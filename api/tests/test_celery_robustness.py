import pytest
from unittest.mock import patch, MagicMock
from db import User, CreditLedger
from tasks import predict_task
from worker import celery_app

@pytest.mark.asyncio
async def test_predict_task_timeout(db_session):
    # Configure Celery to use memory backend and eager execution for tests
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        broker_url='memory://',
        result_backend='cache+memory://'
    )

    # Setup User
    user = User(email="task_fail@example.com", password_hash="hash", credits=10)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    user_id = user.id
    
    # We need to access the synchronous session used in tasks.py
    # Since tasks.py creates its own engine/session, we need to mock it to use our test DB.
    # But our test DB is async. tasks.py uses sync.
    # Verification strategy:
    # We can mock `Session` in tasks.py to return a Mock that we can inspect.
    # We won't assert against the real DB for the side effects (ledger), but against the mock calls.
    
    # Verification strategy:
    # Use predict_task.apply(args=[...], retries=1) to execute logic synchronously and simulate retry state.
    # We patch get_stock_predictions to fail.
    
    with patch("prediction_service_multihead.get_stock_predictions", side_effect=Exception("Simulated Timeout")):
        with patch("tasks.Session") as MockSession:
            # Mock the session context
            mock_session_instance = MagicMock()
            MockSession.return_value.__enter__.return_value = mock_session_instance
            
            # Mock getting the user
            mock_user = MagicMock()
            mock_user.id = user_id
            mock_user.credits = 8 
            mock_session_instance.get.return_value = mock_user
            
            # Use .apply() to execute eagerly with retries set
            # This simulates being in a retry state
            
            try:
                # We expect "Retry Aborted" to bubble up or be handled
                # Since we mocked self.retry to raise it.
                # But wait, if we use .apply(), 'self' is the task instance.
                # We need to ensure 'self.retry' IS mocked on that instance.
                # 'predict_task' is the instance.
                
                with patch.object(predict_task, 'retry', side_effect=Exception("Retry Aborted")):
                     predict_task.apply(args=["AAPL", "multihead", 100, user_id], retries=1)
            
            except Exception as e:
                if str(e) != "Retry Aborted":
                    # If the task raised something else (like the timeout causing a non-retry crash?), 
                    # but we mocked get_stock_predictions to raise.
                    # The code catches it and calls self.retry.
                    raise e
            
            # Verify failure triggered refund logic
            assert mock_user.credits == 10
            assert mock_session_instance.add.call_count >= 1
            # 1. User credits should be refunded
            assert mock_user.credits == 10 # 8 + 2
            
            # 2. Ledger entry added
            assert mock_session_instance.add.call_count >= 1
            # Check the args passed to add
            # We look for CreditLedger object
            found_ledger = False
            for call in mock_session_instance.add.call_args_list:
                arg = call[0][0]
                if isinstance(arg, CreditLedger):
                    assert arg.amount == 2
                    assert arg.reason == "REFUND_FAILED_TASK"
                    found_ledger = True
            
            assert found_ledger, "CreditLedger entry was not added"

