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
def mock_celery_apply_async():
    # Patch the apply_async method on the task
    with patch("tasks.predict_task.apply_async") as mock_apply:
        mock_task = MagicMock()
        mock_task.id = "test-task-id-123"
        mock_apply.return_value = mock_task
        yield mock_apply

@pytest.mark.asyncio
async def test_predict_endpoint_dispatch(client, db_session, mock_celery_apply_async):
    # Setup user and credits
    pwd = hash_password("password")
    user = User(email="test_async@example.com", password_hash=pwd, credits=10)
    db_session.add(user)
    await db_session.commit()
    
    # Login
    auth_resp = await client.post("/api/auth/login", json={"email": "test_async@example.com", "password": "password"})
    token = auth_resp.json()["access_token"]
    
    # Patch UUID to get predictable ID
    fixed_uuid = "test-task-id-123"
    with patch("uuid.uuid4", return_value=fixed_uuid):
        
        # Make Prediction Request
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"ticker": "GOOGL", "model": "multihead", "lookback": 50}
        
        response = await client.post("/api/predict", json=payload, headers=headers)
        
        # Verify Response
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["task_id"] == fixed_uuid
        assert data["status"] == "processing"
        
        # Verify Task Dispatched
        mock_celery_apply_async.assert_called_once()
        # call arguments: args=(...), task_id=...
        call_kwargs = mock_celery_apply_async.call_args[1]
        assert call_kwargs["task_id"] == fixed_uuid
        
        args = call_kwargs["args"]
        assert args[0] == "GOOGL" # ticker
        assert args[3] == user.id # user_id
        
        # Verify Credits Deducted
        await db_session.refresh(user)
        assert user.credits == 8 # 10 - 2

@pytest.mark.asyncio
async def test_polling_endpoint_success(client, db_session):
    # Setup user
    pwd = hash_password("password")
    user = User(email="poll_success@example.com", password_hash=pwd)
    db_session.add(user)
    await db_session.commit()
    
    # Insert PredictionHistory
    task_id = "test-task-id"
    history = PredictionHistory(
        user_id=user.id,
        task_id=task_id,
        ticker="AAPL",
        model_type="multihead"
    )
    db_session.add(history)
    await db_session.commit()
    
    auth_resp = await client.post("/api/auth/login", json={"email": "poll_success@example.com", "password": "password"})
    token = auth_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Patch celery.result.AsyncResult
    with patch("celery.result.AsyncResult") as MockAsyncResult:
        mock_task = MagicMock()
        mock_task.state = "SUCCESS"
        mock_task.result = {"prediction": [100, 101, 102], "metrics": {"rmse": 0.5}}
        MockAsyncResult.return_value = mock_task
        
        response = await client.get(f"/api/predict/{task_id}", headers=headers)
        
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "completed"
        assert "result" in data
        assert data["result"]["prediction"] == [100, 101, 102]

@pytest.mark.asyncio
async def test_polling_endpoint_processing(client, db_session):
    # Setup user
    pwd = hash_password("password")
    user = User(email="poll_proc@example.com", password_hash=pwd)
    db_session.add(user)
    await db_session.commit()
    
    task_id = "processing-id"
    history = PredictionHistory(
        user_id=user.id,
        task_id=task_id,
        ticker="AAPL",
        model_type="multihead"
    )
    db_session.add(history)
    await db_session.commit()
    
    auth_resp = await client.post("/api/auth/login", json={"email": "poll_proc@example.com", "password": "password"})
    token = auth_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    with patch("celery.result.AsyncResult") as MockAsyncResult:
        mock_task = MagicMock()
        mock_task.state = "PENDING" 
        MockAsyncResult.return_value = mock_task
        
        response = await client.get(f"/api/predict/{task_id}", headers=headers)
        
        assert response.status_code == 200
        assert response.json()["status"] == "processing"

def test_predict_task_execution():
    # Test the worker task logic directly (synchronous part)
    mock_ml_result = {
        "metrics": {"directional_accuracy": 60.0},
        "forecast": [150, 151, 152]
    }
    
    user_id = 999
    
    # Patch db_session instead of Session
    with patch("tasks.db_session") as mock_session_instance:
        # Simulate that no existing history is found so it creates a new one
        mock_session_instance.scalar.return_value = None
        
        # Mock the ML service import
        with patch.dict("sys.modules", {"prediction_service_multihead": MagicMock()}):
            import sys
            mock_ml_module = sys.modules["prediction_service_multihead"]
            mock_ml_module.get_stock_predictions.return_value = mock_ml_result
            
            # Run task
            res = predict_task(ticker="MSFT", model_type="multihead", lookback=60, user_id=user_id)
            
            assert res == mock_ml_result
            
            # Verify DB additions
            assert mock_session_instance.add.called
            # The code adds history_entry
            added_obj = mock_session_instance.add.call_args[0][0]
            assert isinstance(added_obj, PredictionHistory)
            assert added_obj.ticker == "MSFT"
            assert added_obj.user_id == user_id
