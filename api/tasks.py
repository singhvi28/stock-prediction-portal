from worker import celery_app
import os
import redis
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, select
from db import User, Transaction, CreditLedger
from datetime import datetime

# Use Sync Engine for Celery
DATABASE_URL = os.getenv("DATABASE_URL").replace("+asyncpg", "")
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
                from db import PredictionHistory, CreditLedger, User
                
                acc = result_data.get('metrics', {}).get('directional_accuracy')
                
                history_entry = PredictionHistory(
                    user_id=user_id,
                    ticker=ticker.upper(),
                    model_type=model_type,
                    directional_accuracy=acc,
                    prediction_data=result_data
                )
                session.add(history_entry)
        
        return result_data

    except Exception as e:
        # Refund credits on failure
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
            
        raise self.retry(exc=e, max_retries=1)
