from worker import celery_app
import os
import redis
from celery.signals import worker_process_init
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, scoped_session
from db import User, Transaction, CreditLedger, PredictionHistory
from datetime import datetime

# Global Session (initialized per worker process)
db_session = None

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.Redis.from_url(REDIS_URL)

@worker_process_init.connect
def init_worker(**kwargs):
    """
    Called once when each worker process starts.
    We create one persistent engine and one session factory here.
    """
    global db_session
    DATABASE_URL = os.getenv("DATABASE_URL").replace("+asyncpg", "").replace("+aiosqlite", "")
    
    # Pool size controls how many connections each worker keeps open
    engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)
    session_factory = sessionmaker(bind=engine)
    
    # scoped_session ensures each thread in the worker gets the same session
    db_session = scoped_session(session_factory)
    print(f"Worker process initialized with DB pool.")

@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, queue='payments')
def process_payment(self, payment_id: str, order_id: str):
    # Idempotency Check
    if redis_client.get(f"processed:{payment_id}"):
        return "Already Processed"

    # Locking
    lock_key = f"lock:{payment_id}"
    lock = redis_client.lock(lock_key, timeout=30)
    
    if not lock.acquire(blocking=False):
        raise self.retry(exc=Exception("Locked"))
    
    if db_session is None:
        raise Exception("DB Session not initialized")

    try:
        # Use the persistent worker session
        # 1. Get Transaction
        txn = db_session.scalar(select(Transaction).where(Transaction.razorpay_order_id == order_id))
        
        if not txn:
                print(f"Transaction not found for order {order_id}")
                return "Transaction Not Found"
        
        if txn.status == "SUCCESS":
                return "Already Success"

        # 2. Update Status
        txn.status = "SUCCESS"
        txn.razorpay_payment_id = payment_id
        
        # 3. Add Credits
        user = db_session.get(User, txn.user_id)
        if user:
            user.credits += txn.credits
            
            # 4. Ledger
            ledger = CreditLedger(
                user_id=user.id,
                transaction_id=txn.id,
                amount=txn.credits,
                reason="PURCHASE"
            )
            db_session.add(ledger)
        
        db_session.commit()
        
        # Mark as processed in Redis (TTL 7 days)
        redis_client.setex(f"processed:{payment_id}", 604800, "1")
        return "Payment Processed"

    except Exception as e:
        db_session.rollback()
        print(f"Error processing payment: {e}")
        raise self.retry(exc=e)
    finally:
        db_session.remove()
        try:
            lock.release()
        except redis.exceptions.LockError:
            pass

@celery_app.task(bind=True, queue='ml')
def predict_task(self, ticker: str, model_type: str, lookback: int, user_id: int):
    if db_session is None:
        raise Exception("DB Session not initialized")

    try:
        if model_type == "additive":
            from prediction_service_additive import get_stock_predictions
        else:
            from prediction_service_multihead import get_stock_predictions
        
        result_data = get_stock_predictions(ticker.upper(), lookback=lookback, epochs=15)
        
        if "error" in result_data:
            raise Exception(result_data["error"])
            
        # Save to DB
        # Check for existing history record created by main.py
        stmt = select(PredictionHistory).where(PredictionHistory.task_id == self.request.id)
        history_entry = db_session.scalar(stmt)
        
        acc = result_data.get('metrics', {}).get('directional_accuracy')

        if history_entry:
            # Update existing
            history_entry.prediction_data = result_data
            history_entry.directional_accuracy = acc
        else:
            # Fallback
            print(f"Warning: history not found for task {self.request.id}. Creating new.")
            history_entry = PredictionHistory(
                user_id=user_id,
                task_id=self.request.id,
                ticker=ticker.upper(),
                model_type=model_type,
                directional_accuracy=acc,
                prediction_data=result_data
            )
            db_session.add(history_entry)
        
        db_session.commit()
        return result_data

    except Exception as e:
        db_session.rollback()
        
        # Refund Logic on Failure
        current_retries = self.request.retries or 0
        max_retries_limit = 1 
        
        if current_retries >= max_retries_limit:
            try:
                cost = 3 if model_type == "additive" else 2
                user = db_session.get(User, user_id)
                if user:
                    user.credits += cost
                    db_session.add(CreditLedger(
                        user_id=user_id,
                        amount=cost,
                        reason="REFUND_FAILED_TASK"
                    ))
                    
                    # Update History to show failure and refund
                    stmt = select(PredictionHistory).where(PredictionHistory.task_id == self.request.id)
                    history_entry = db_session.scalar(stmt)
                    if history_entry:
                        history_entry.prediction_data = {
                            "status": "failed", 
                            "error": str(e), 
                            "refunded": True
                        }
                        
                    db_session.commit()
            except Exception as refund_err:
                db_session.rollback()
                print(f"Failed to refund: {refund_err}")
            
        raise self.retry(exc=e, max_retries=max_retries_limit)
    finally:
        db_session.remove()

@celery_app.task(bind=True)
def cleanup_stuck_tasks(self):
    """
    Periodic task to find prediction requests that are stuck in 'processing' 
    (prediction_data is NULL) for more than 24 hours.
    Marks them as failed and refunds credits.
    """
    from datetime import timedelta
    
    if db_session is None:
        return "DB Session not initialized"

    try:
        # Find stuck tasks
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        stmt = select(PredictionHistory).where(
            PredictionHistory.prediction_data == None,
            PredictionHistory.created_at < cutoff_time
        )
        stuck_tasks = db_session.scalars(stmt).all()
        
        refund_count = 0
        
        for task in stuck_tasks:
            print(f"Cleaning up stuck task: {task.task_id}")
            
            # 1. Mark as failed
            task.prediction_data = {
                "status": "failed", 
                "error": "Task timed out (24h cleanup)",
                "refunded": True
            }
            
            # 2. Refund
            cost = 3 if task.model_type == "additive" else 2
            user = db_session.get(User, task.user_id)
            
            if user:
                user.credits += cost
                db_session.add(CreditLedger(
                    user_id=user.id,
                    amount=cost,
                    reason="REFUND_STUCK_TASK"
                ))
                refund_count += 1
        
        db_session.commit()
        return f"Cleaned up {refund_count} stuck tasks."

    except Exception as e:
        db_session.rollback()
        print(f"Error in cleanup task: {e}")
        return f"Error: {e}"
    finally:
        db_session.remove()
