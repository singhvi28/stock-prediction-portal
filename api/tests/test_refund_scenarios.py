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
    Reproduces the bug where a user is refunded on EACH failure.
    """
    user_id = 123
    initial_credits = 10
    cost = 2
    real_user = SimpleUser(user_id, initial_credits)
    
    with patch("prediction_service_multihead.get_stock_predictions", side_effect=Exception("Crash")):
        
        mock_session = MagicMock()
        mock_session.get.return_value = real_user
        
        with patch("tasks.Session") as MockSessionClass:
            MockSessionClass.return_value.__enter__.return_value = mock_session
            
            # We patch the 'retry' method on the Task object itself
            # We need to ensure we patch the exact object imported
            with patch.object(predict_task, "retry", side_effect=Exception("RetryInterrupt")) as mock_retry:
            
                # --- RUN 1 ---
                try:
                    predict_task("AAPL", "multihead", 30, user_id)
                except Exception as e:
                    if str(e) != "RetryInterrupt":
                         print(f"Caught unexpected: {e}") 
                
                # Check credit update
                assert real_user.credits == 12, "Refund 1 failed."
                
                # --- RUN 2 ---
                try:
                    predict_task("AAPL", "multihead", 30, user_id)
                except Exception:
                    pass
                    
                # The Bug: Credits updated again
                assert real_user.credits == 14, "Double Refund Bug NOT reproduced."
                
                print("[BUG PROVEN] Double refund confirmed.")

def test_refund_db_failure():
    with patch("prediction_service_multihead.get_stock_predictions", side_effect=Exception("Crash")):
        with patch("tasks.Session") as MockSessionClass:
            mock_session = MagicMock()
            mock_session.__enter__.side_effect = Exception("DB Fail")
            MockSessionClass.return_value = mock_session
            
            with patch.object(predict_task, "retry", side_effect=Exception("RetryInterrupt")) as mock_retry:
                try:
                    predict_task("AAPL", "multihead", 30, 123)
                except Exception:
                    pass
                
                assert mock_retry.called, "Should retry despite DB failure"
