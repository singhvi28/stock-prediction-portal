from worker import celery_app
import os
import redis
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, select
from db import User, Transaction, CreditLedger
from datetime import datetime

# Use Sync Engine for Celery
DATABASE_URL = os.getenv("DATABASE_URL").replace("+asyncpg", "").replace("+aiosqlite", "")
engine = create_engine(DATABASE_URL)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.Redis.from_url(REDIS_URL)

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_payment(self, payment_id: str, order_id: str):
    # Idempotency Check
    if redis_client.get(f"processed:{payment_id}"):
        return "Already Processed"

    # Locking
    lock_key = f"lock:{payment_id}"
    lock = redis_client.lock(lock_key, timeout=30)
    
    if not lock.acquire(blocking=False):
        # Retry if locked
        raise self.retry(exc=Exception("Locked"))
    
    try:
        with Session(engine) as session:
            with session.begin():
                # 1. Get Transaction
                # razorpay_order_id matches the order_id from webhook
                txn = session.scalar(select(Transaction).where(Transaction.razorpay_order_id == order_id))
                
                if not txn:
                     print(f"Transaction not found for order {order_id}")
                     return "Transaction Not Found"
                
                if txn.status == "SUCCESS":
                     return "Already Success"

                # 2. Update Status
                txn.status = "SUCCESS"
                txn.razorpay_payment_id = payment_id
                
                # 3. Add Credits
                user = session.get(User, txn.user_id)
                if user:
                    user.credits += txn.credits
                    
                    # 4. Ledger
                    ledger = CreditLedger(
                        user_id=user.id,
                        transaction_id=txn.id,
                        amount=txn.credits,
                        reason="PURCHASE"
                    )
                    session.add(ledger)
                
        # Mark as processed in Redis (TTL 7 days)
        redis_client.setex(f"processed:{payment_id}", 604800, "1")
        return "Payment Processed"

    except Exception as e:
        # DB rollback is handled by session context manager
        print(f"Error processing payment: {e}")
        self.retry(exc=e)
    finally:
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass # Lock might have expired or released

@celery_app.task(bind=True)
def predict_task(self, ticker: str, model_type: str, lookback: int, user_id: int):
    try:
        if model_type == "additive":
            from prediction_service_additive import get_stock_predictions
        else:
            from prediction_service_multihead import get_stock_predictions
        
        result_data = get_stock_predictions(ticker.upper(), lookback=lookback, epochs=15)
        
        if "error" in result_data:
            raise Exception(result_data["error"])
            
        # Save to DB
        with Session(engine) as session:
            with session.begin():
                from db import PredictionHistory # Keep PredictionHistory if not global
                
                # Check for existing history record created by main.py
                stmt = select(PredictionHistory).where(PredictionHistory.task_id == self.request.id)
                history_entry = session.scalar(stmt)
                
                acc = result_data.get('metrics', {}).get('directional_accuracy')

                if history_entry:
                    # Update existing
                    history_entry.prediction_data = result_data
                    history_entry.directional_accuracy = acc
                    # ticker/model_type/user_id should match, but we can update to be sure or just save
                else:
                    # Fallback: Create new (though main.py should have created it)
                    print(f"Warning: history not found for task {self.request.id}. Creating new.")
                    history_entry = PredictionHistory(
                        user_id=user_id,
                        task_id=self.request.id, # Ensure we save task_id
                        ticker=ticker.upper(),
                        model_type=model_type,
                        directional_accuracy=acc,
                        prediction_data=result_data
                    )
                    session.add(history_entry)
        
        return result_data

    except Exception as e:
        # Only refund if this is the final retry attempt
        # self.request.retries starts at 0. If max_retries is 1, we retry once.
        # Logic: If retries < max_retries, we are about to retry, so DONT refund yet.
        # If retries >= max_retries, we are abandoning, so DO refund.
        
        # Note: self.retry raises an exception to stop execution.
        # We need to know if self.retry WILL succeed in scheduling a retry.
        
        current_retries = self.request.retries or 0
        max_retries_limit = 1 # As defined in the retry call below
        
        if current_retries >= max_retries_limit:
            try:
                 with Session(engine) as session:
                    with session.begin():
                        cost = 3 if model_type == "additive" else 2
                        user = session.get(User, user_id)
                        if user:
                            user.credits += cost
                            session.add(CreditLedger(
                                user_id=user_id,
                                amount=cost,
                                reason="REFUND_FAILED_TASK"
                            ))
            except Exception as refund_err:
                print(f"Failed to refund: {refund_err}")
            
        raise self.retry(exc=e, max_retries=max_retries_limit)
