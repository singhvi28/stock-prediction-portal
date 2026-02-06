import pytest
from httpx import AsyncClient
from unittest.mock import patch
from sqlalchemy import select
from db import User, CreditLedger

@pytest.mark.asyncio
async def test_insufficient_credits(client: AsyncClient, db_session):
    # 1. Register and Login
    auth_payload = {"email": "poor@example.com", "password": "pass"}
    await client.post("/api/auth/register", json=auth_payload)
    login_res = await client.post("/api/auth/login", json=auth_payload)
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Manually reduce credits to 1
    result = await db_session.execute(select(User).where(User.email == "poor@example.com"))
    user = result.scalars().first()
    user.credits = 1
    await db_session.commit()

    # 3. Try to predict (Multihead costs 2)
    payload = {"ticker": "AAPL", "model": "multihead"}
    response = await client.post("/api/predict", json=payload, headers=headers)

    assert response.status_code == 402
    assert response.json()["detail"] == "Insufficient credits. 2 credits required."

@pytest.mark.asyncio
async def test_credit_deduction_multihead(client: AsyncClient, db_session):
    # 1. Register (Starts with 5 credits)
    auth_payload = {"email": "rich@example.com", "password": "pass"}
    await client.post("/api/auth/register", json=auth_payload)
    login_res = await client.post("/api/auth/login", json=auth_payload)
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Mock Prediction
    mock_result = {
        "ticker": "AAPL",
        "metrics": {"rmse": 10},
        "model_historical_predictions": [],
        "forecast_prices": []
    }

    with patch("prediction_service_multihead.get_stock_predictions", return_value=mock_result):
        payload = {"ticker": "AAPL", "model": "multihead"}
        response = await client.post("/api/predict", json=payload, headers=headers)
        
        assert response.status_code == 200

    # 3. Verify Credits (5 - 2 = 3)
    # Re-fetch user
    db_session.expire_all()
    result = await db_session.execute(select(User).where(User.email == "rich@example.com"))
    user = result.scalars().first()
    assert user.credits == 3

    # 4. Verify Ledger
    ledger_res = await db_session.execute(select(CreditLedger).where(CreditLedger.user_id == user.id))
    entry = ledger_res.scalars().first()
    assert entry is not None
    assert entry.amount == -2
    assert entry.reason == "PREDICTION_MULTIHEAD"

@pytest.mark.asyncio
async def test_credit_deduction_additive(client: AsyncClient, db_session):
    # 1. Register (Starts with 5 credits)
    auth_payload = {"email": "additive@example.com", "password": "pass"}
    await client.post("/api/auth/register", json=auth_payload)
    login_res = await client.post("/api/auth/login", json=auth_payload)
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Mock Prediction
    mock_result = {
        "ticker": "MSFT",
        "metrics": {"rmse": 10},
        "model_historical_predictions": [],
        "forecast_prices": []
    }

    with patch("prediction_service_additive.get_stock_predictions", return_value=mock_result):
        payload = {"ticker": "MSFT", "model": "additive"}
        response = await client.post("/api/predict", json=payload, headers=headers)
        
        assert response.status_code == 200

    # 3. Verify Credits (5 - 3 = 2)
    db_session.expire_all()
    result = await db_session.execute(select(User).where(User.email == "additive@example.com"))
    user = result.scalars().first()
    assert user.credits == 2

@pytest.mark.asyncio
async def test_refund_on_failure(client: AsyncClient, db_session):
    # 1. Register
    auth_payload = {"email": "fail@example.com", "password": "pass"}
    await client.post("/api/auth/register", json=auth_payload)
    login_res = await client.post("/api/auth/login", json=auth_payload)
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Mock Failure
    with patch("prediction_service_multihead.get_stock_predictions", side_effect=Exception("Model Crashed")):
        payload = {"ticker": "FAIL", "model": "multihead"}
        response = await client.post("/api/predict", json=payload, headers=headers)
        
        assert response.status_code == 500

    # 3. Verify Credits (Should still be 5)
    db_session.expire_all()
    result = await db_session.execute(select(User).where(User.email == "fail@example.com"))
    user = result.scalars().first()
    assert user.credits == 5

    # 4. Verify Ledger (Purchase + Refund)
    # Actually, the logic adds 2 entries: one for purchase (-2) and one for refund (+2).
    # Wait, the first transaction commits BEFORE the try/except block in the API code? 
    # Let's check api/main.py logic. 
    # Yes: db.add(ledger); await db.commit() happens BEFORE prediction.
    # So we expect 2 entries in ledger.
    
    ledger_res = await db_session.execute(select(CreditLedger).where(CreditLedger.user_id == user.id))
    entries = ledger_res.scalars().all()
    assert len(entries) == 2
    reasons = [e.reason for e in entries]
    assert "PREDICTION_MULTIHEAD" in reasons
    assert "REFUND_FAILED_PREDICTION" in reasons
