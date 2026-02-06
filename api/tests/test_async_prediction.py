import pytest
from unittest.mock import patch, MagicMock
from httpx import ASGITransport, AsyncClient
from main import app, get_db
from tasks import predict_task
from db import User, CreditLedger, PredictionHistory
from sqlalchemy import select
from utils import hash_password

# Mock the Celery task delay
@pytest.fixture
def mock_celery_delay():
    # Patch where the tasks module is imported in main.py
    # Since main.py does "from tasks import predict_task", we need to patch tasks.predict_task
    # But wait, predict_task is imported inside the function in main.py.
    # So we should patch "tasks.predict_task.delay".
    with patch("tasks.predict_task.delay") as mock_delay:
        mock_task = MagicMock()
        mock_task.id = "test-task-id-123"
        mock_delay.return_value = mock_task
        yield mock_delay

@pytest.mark.asyncio
async def test_predict_endpoint_dispatch(client, db_session, mock_celery_delay):
    # Setup user and credits
    # Use real hash_password to generate valid salt
    pwd = hash_password("password")
    user = User(email="test_async@example.com", password_hash=pwd, credits=10)
    db_session.add(user)
    await db_session.commit()
    
    # Login
    auth_resp = await client.post("/api/auth/login", json={"email": "test_async@example.com", "password": "password"})
    token = auth_resp.json()["access_token"]
    
    # Make Prediction Request
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"ticker": "GOOGL", "model": "multihead", "lookback": 50}
    
    response = await client.post("/api/predict", json=payload, headers=headers)
    
    # Verify Response
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["task_id"] == "test-task-id-123"
    assert data["status"] == "processing"
    
    # Verify Task Dispatched
    mock_celery_delay.assert_called_once()
    args = mock_celery_delay.call_args[0]
    assert args[0] == "GOOGL" # ticker
    assert args[1] == "multihead" # model
    assert args[2] == 50 # lookback
    assert args[3] == user.id # user_id
    
    # Verify Credits Deducted
    await db_session.refresh(user)
    assert user.credits == 8 # 10 - 2

@pytest.mark.asyncio
async def test_polling_endpoint_success(client, db_session):
    # Patch celery.result.AsyncResult instead of main.AsyncResult
    with patch("celery.result.AsyncResult") as MockAsyncResult:
        mock_task = MagicMock()
        mock_task.state = "SUCCESS"
        mock_task.result = {"prediction": [100, 101, 102], "metrics": {"rmse": 0.5}}
        MockAsyncResult.return_value = mock_task
        
        response = await client.get("/api/predict/test-task-id")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert "result" in data
        assert data["result"]["prediction"] == [100, 101, 102]

@pytest.mark.asyncio
async def test_polling_endpoint_processing(client):
    with patch("celery.result.AsyncResult") as MockAsyncResult:
        mock_task = MagicMock()
        mock_task.state = "PENDING" 
        MockAsyncResult.return_value = mock_task
        
        response = await client.get("/api/predict/processing-id")
        
        assert response.status_code == 200
        assert response.json()["status"] == "processing"

def test_predict_task_execution():
    # Test the worker task logic directly (synchronous part)
    # We need to mock the ML service imports inside the function
    
    mock_ml_result = {
        "metrics": {"directional_accuracy": 60.0},
        "forecast": [150, 151, 152]
    }
    
    # We also need to mock the Sync DB Session used in tasks.py
    # Since tasks.py uses its own engine/session, we should mock 'tasks.Session'
    
    with patch("tasks.get_stock_predictions", create=True) as mock_ml:
        # NOTE: logic imports dynamically, so we might need to patch 'sys.modules' or use patch.dict
        # Simpler: Mock the imported module in sys.modules if it was global, but it's local.
        # Actually easier to patch 'prediction_service_multihead.get_stock_predictions' 
        # but we must ensure it's imported.
        pass

    # Better approach for task testing: 
    # The task uses `Session(engine)`. We should mock `tasks.Session` to return a mock session
    # that we can inspect.
    
    user_id = 999
    
    with patch("tasks.Session") as MockSession:
        mock_session_instance = MockSession.return_value.__enter__.return_value
        mock_session_instance.begin.return_value.__enter__.return_value = None # Context manager
        
        # Mock the ML service import
        with patch.dict("sys.modules", {"prediction_service_multihead": MagicMock()}):
            import sys
            mock_ml_module = sys.modules["prediction_service_multihead"]
            mock_ml_module.get_stock_predictions.return_value = mock_ml_result
            
            # Run task
            res = predict_task(ticker="MSFT", model_type="multihead", lookback=60, user_id=user_id)
            
            assert res == mock_ml_result
            
            # Verify DB additions
            # call_args_list for session.add
            assert mock_session_instance.add.called
            added_obj = mock_session_instance.add.call_args[0][0]
            assert isinstance(added_obj, PredictionHistory)
            assert added_obj.ticker == "MSFT"
            assert added_obj.user_id == user_id
