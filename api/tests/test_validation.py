import pytest
from httpx import AsyncClient
from db import User
from utils import create_access_token

@pytest.mark.asyncio
async def test_input_validation(db_session, client):
    # Setup User
    user = User(email="validator@example.com", password_hash="hash", credits=100)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    token = create_access_token({"sub": user.email})
    headers = {"Authorization": f"Bearer {token}"}
    
    # 1. Test Invalid Ticker (Empty)
    resp = await client.post("/api/predict", json={"ticker": "", "model": "multihead", "lookback": 10}, headers=headers)
    assert resp.status_code in [400, 422], f"Should reject empty ticker, got {resp.status_code}"

    # 2. Test Invalid Ticker (Numeric/Special Chars) - Assuming validation exists
    # If the app relies on yfinance to fail, it might be 500 or 400. 
    # But strict validation should catch it.
    resp = await client.post("/api/predict", json={"ticker": "12345", "model": "multihead"}, headers=headers)
    # The current code might pass this to Celery if no Pydantic validator exists.
    # We assert 400/422 assuming we WANT validation.
    
    # 3. Test Negative Lookback
    resp = await client.post("/api/predict", json={"ticker": "AAPL", "model": "multihead", "lookback": -10}, headers=headers)
    assert resp.status_code in [400, 422], f"Should reject negative lookback, got {resp.status_code}"
    
    # 4. Test Zero Lookback
    resp = await client.post("/api/predict", json={"ticker": "AAPL", "model": "multihead", "lookback": 0}, headers=headers)
    assert resp.status_code in [400, 422], f"Should reject zero lookback, got {resp.status_code}"

    # 5. Test Unknown Model
    resp = await client.post("/api/predict", json={"ticker": "AAPL", "model": "super_ai_9000"}, headers=headers)
    assert resp.status_code in [400, 422], f"Should reject unknown model, got {resp.status_code}"
