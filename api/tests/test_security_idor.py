import pytest
from httpx import AsyncClient
from db import User, PredictionHistory
from utils import create_access_token
from main import app
from sqlalchemy import select

@pytest.mark.asyncio
async def test_get_prediction_status_unauthorized(db_session, client):
    # 1. Setup Victim User
    victim = User(email="victim@example.com", password_hash="hash", credits=10)
    db_session.add(victim)
    await db_session.commit()
    await db_session.refresh(victim)
    
    # 2. Setup Attacker User
    attacker = User(email="attacker@example.com", password_hash="hash", credits=10)
    db_session.add(attacker)
    await db_session.commit()
    await db_session.refresh(attacker)
    
    # 3. Victim creates a "task" (simulated by creating a PredictionHistory entry or mocking)
    # Since status endpoint might check DB or Redis. 
    # If checking DB (History), we create an entry.
    # If checking Redis (Processing), we mock.
    # Let's assume the endpoint checks Redis/Celery for status processing, OR DB for history.
    # The requirement says "GET /api/predict/{task_id}".
    # Let's inspect main.py to see how it's implemented.
    # 3. Victim has a task
    # We simulate a task that belongs to the victim.
    # Since the current implementation doesn't check DB ownership, we just need a task_id 
    # and we need to ensure the system *knows* it belongs to the victim if we add protection.
    # Currently, the system DOES NOT know who owns a task_id unless we store it in PredictionHistory or similar.
    # The `predict` endpoint stores `CreditLedger` but not `PredictionHistory` until the task *completes* (in `tasks.py`)?
    # Let's check `tasks.py`.
    # If the task is running, there's no DB record linking task_id to user_id accessible to the GET endpoint efficiently 
    # unless we add it. 
    # BUT, `PredictionHistory` might be created at start?
    # Inspecting `tasks.py`... 
    
    # For now, let's write the test assuming we SHOULD reject it.
    # We can mock `AsyncResult` to return a result, but the Auth check happens *before* or *during* lookup.
    
    # Generate tokens
    victim_token = create_access_token({"sub": victim.email})
    attacker_token = create_access_token({"sub": attacker.email})
    
    # 4. Attacker tries to access arbitrary task ID
    # In a real IDOR, we'd access a known task ID.
    task_id = "victim-task-123"
    
    # We might need to mock the Celery result to avoid 404 from backend if it checks exists
    # OR the endpoint might just return "PENDING" for unknown IDs if using standard Celery.
    
    # The current code:
    # result = AsyncResult(task_id)
    # if result.state == ...
    
    # We need to simulate that "victim-task-123" belongs to Victim.
    # If we implement protection, we likely will require `task_id` to be stored in DB with `user_id`.
    # So let's insert a record into PredictionHistory/JobTable if it exists.
    # Checking imports... PredictionHistory.
    
    # Let's insert a fake history record to claim ownership?
    history = PredictionHistory(
        user_id=victim.id,
        ticker="AAPL",
        model_type="multihead",
        directional_accuracy=0.99,
        prediction_data={"predicted_price": 150.0, "actual_price": 151.0},
        task_id=task_id 
    )
    db_session.add(history)
    await db_session.commit()
    # Check PredictionHistory model
    # I need to see if `task_id` is a column in PredictionHistory.
    
    # 4. Mock the task result in Celery/Redis
    # The endpoint checks AsyncResult(task_id).state
    # We need to ensure that when the code calls AsyncResult, it finds something.
    # Since we are using real Celery in tests (memory backend), we can actually "dispatch" a task 
    # OR we can mock AsyncResult.
    
    # Let's mock AsyncResult because we don't want to rely on the worker actually picking up a fake task_id.
    # And we want to test the *endpoint logic*, not the worker.
    
    from unittest.mock import patch, MagicMock
    
    with patch("celery.result.AsyncResult") as MockAsyncResult:
        mock_result = MagicMock()
        mock_result.state = "SUCCESS"
        mock_result.result = {"prediction": 100}
        MockAsyncResult.return_value = mock_result
        
        # 5. Attacker requests status
        response = await client.get(
            f"/api/predict/{task_id}",
            headers={"Authorization": f"Bearer {attacker_token}"}
        )
        
        # 6. Verify Access Denied
        # WE EXPECT THIS TO SUCCEED (200) currently because the code is vulnerable.
        # But the TEST requirement is to ensure it PREVENTS data leakage.
        # So we assert 403.
        # This test WILL FAIL until we fix the bug.
        
        print(f"DEBUG: Endpoint returned {response.status_code}")
        assert response.status_code in [403, 404], \
            f"IDOR Failed: Attacker was able to view task status! Got {response.status_code} {response.json()}"
