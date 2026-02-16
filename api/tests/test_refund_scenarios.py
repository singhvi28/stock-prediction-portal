import pytest
from unittest.mock import patch, MagicMock
from tasks import predict_task
# predict_task is the Celery Task instance

class SimpleUser:
    def __init__(self, uid, credits):
        self.id = uid
        self.credits = credits

def test_double_refund_on_retry():
    """
    Verifies that we DO NOT refund on intermediate retries,
    and ONLY refund on the final failure (or when max retries hit).
    """
    user_id = 123
    initial_credits = 10
    cost = 2
    real_user = SimpleUser(user_id, initial_credits)
    
    with patch("prediction_service_multihead.get_stock_predictions", side_effect=Exception("Crash")):
        
        mock_session = MagicMock()
        mock_session.get.return_value = real_user
        
        # Patch the global db_session
        with patch("tasks.db_session", mock_session):
            
            # Patch the 'retry' method on the Task object so it raises our interrupt
            with patch.object(predict_task, "retry", side_effect=Exception("RetryInterrupt")) as mock_retry:
                
                # Setup request mock if not inherently present in this context
                if not hasattr(predict_task, "request") or predict_task.request is None:
                    predict_task.request = MagicMock()
                
                # --- RUN 1 (Retry Count: 0) ---
                # We expect NO refund here because we retry.
                # Credits should stay 10.
                
                predict_task.request.retries = 0
                
                try:
                    predict_task("AAPL", "multihead", 30, user_id)
                except Exception as e:
                    if str(e) != "RetryInterrupt":
                         pass 
                
                # Check credit update - Should be 10 (NO REFUND)
                assert real_user.credits == 10, f"Credits refunded prematurely! Got {real_user.credits}"
                
                # --- RUN 2 (Retry Count: 1 - Max) ---
                # We expect Refund here.
                # Credits 10 -> 12.
                
                predict_task.request.retries = 1
                
                try:
                    predict_task("AAPL", "multihead", 30, user_id)
                except Exception:
                    pass
                    
                # The Bug Fix Verification: Credits updated ONLY now
                assert real_user.credits == 12, f"Refund failed on max retries. Got {real_user.credits}"
                
                print("[SUCCESS] Refund logic validated: No refund on retry, Refund on max retries.")

def test_refund_db_failure():
    with patch("prediction_service_multihead.get_stock_predictions", side_effect=Exception("Crash")):
        with patch("tasks.db_session") as mock_session:
            # Make the first DB call fail
            mock_session.scalar.side_effect = Exception("DB Fail")
            
            with patch.object(predict_task, "retry", side_effect=Exception("RetryInterrupt")) as mock_retry:
                try:
                    predict_task("AAPL", "multihead", 30, 123)
                except Exception:
                    pass
                
                assert mock_retry.called, "Should retry despite DB failure"
