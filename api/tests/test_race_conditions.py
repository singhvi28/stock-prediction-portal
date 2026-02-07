import pytest
import asyncio
from httpx import AsyncClient
from db import User, CreditLedger
from utils import create_access_token
from main import app
from sqlalchemy import select, update

from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_credit_race_condition(db_session, client):
    # Mock predict_task.delay to avoid Redis connection
    # Since predict_task is imported INSIDE the function in main.py, we can't patch main.predict_task easily
    # unless we patch 'tasks.predict_task.delay' which is globally what is used.
    with patch("tasks.predict_task.delay") as mock_delay:
        # Create a mock that returns a task-like object with an id
        mock_result = MagicMock()
        mock_result.id = "test-task-id"
        mock_delay.return_value = mock_result
        
        # 1. Setup User with 5 credits
        # 3 credits usually required for "additive" model. 
        # If we have 5, we can afford 1 request (cost 3) but not 2 (cost 6).
        
        user = User(email="race@example.com", password_hash="hash", credits=5)
        db_session.add(user)
        await db_session.commit()
        await db_session.refresh(user)
        # Commit again to release shared lock from refresh, preventing deadlock with 'for update' in request
        await db_session.commit()
        
        token = create_access_token({"sub": user.email})
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Prepare request function
        async def make_request():
            return await client.post(
                "/api/predict",
                json={"ticker": "AAPL", "model": "additive", "lookback": 10},
                headers=headers
            )

        # 1.5 Sequential Check
        # Verify we can make a successful request first
        print("DEBUG: Running sequential check")
        seq_resp = await make_request()
        print(f"DEBUG: Sequential Response Status: {seq_resp.status_code}")
        print(f"DEBUG: Sequential Response Body: {seq_resp.text}")
        if seq_resp.status_code != 200:
            with open("error.log", "w") as f:
                f.write(seq_resp.text)
        assert seq_resp.status_code == 200, "Sequential request failed"
        
        # Restore credits for race condition test
        await db_session.execute(
            update(User)
            .where(User.email == "race@example.com")
            .values(credits=5)
        )
        await db_session.commit()
        print("DEBUG: Credits restored to 5")

        # 3. Setup for concurrent requests
        # To properly test race conditions, we need separate sessions per request
        # (like real concurrent requests would have)
        
        # Clean up standard override
        app.dependency_overrides.clear()
        
        # Define new override that creates fresh sessions
        engine_used = db_session.bind
        from sqlalchemy.ext.asyncio import async_sessionmaker
        TestSessionMaker = async_sessionmaker(bind=engine_used, expire_on_commit=False)
        
        async def override_get_db_concurrency():
            async with TestSessionMaker() as session:
                yield session
                
        from db import get_db
        app.dependency_overrides[get_db] = override_get_db_concurrency
        
        # 4. Fire concurrent requests
        print("DEBUG: Starting concurrent requests")
        responses = await asyncio.gather(make_request(), make_request())
        
        # 5. Verify Results
        # One should succeed (200), one should fail (402 Payment Required).
        # If both succeed, we have a race condition (double spend).
        
        status_codes = [r.status_code for r in responses]
        print(f"DEBUG: Status codes: {status_codes}")
        for i, r in enumerate(responses):
            if r.status_code != 200:
                print(f"DEBUG: Response {i} ({r.status_code}): {r.text}")

        assert 402 in status_codes, f"One request should fail with 402, got {status_codes}"
        assert status_codes.count(200) == 1, f"Only one request should succeed, got {status_codes}"
        
        # 6. Verify credits
        # Refresh user in a new session to see committed changes
        async with TestSessionMaker() as fresh_session:
            result = await fresh_session.execute(
                select(User).where(User.email == "race@example.com")
            )
            refreshed_user = result.scalar_one()
            print(f"DEBUG: Final credits: {refreshed_user.credits}")
            assert refreshed_user.credits == 2, f"Expected 2 credits (5-3), got {refreshed_user.credits}"
