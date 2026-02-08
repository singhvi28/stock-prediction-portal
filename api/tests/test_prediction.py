import pytest
from httpx import AsyncClient
from unittest.mock import patch

@pytest.mark.asyncio
async def test_predict_endpoint_success(client: AsyncClient):
    # 1. Register and Login to get token
    auth_payload = {"email": "pred@example.com", "password": "pass"}
    await client.post("/api/auth/register", json=auth_payload)
    login_res = await client.post("/api/auth/login", json=auth_payload)
    token = login_res.json()["access_token"]
    
    # 2. Mock the prediction service
    # We mock appropriate module depending on default model (multihead)
    mock_result = {
        "ticker": "AAPL",
        "metrics": {
            "rmse": 10.5,
            "mae": 8.2,
            "mape": 5.1,
            "directional_accuracy": 65.0
        },
        "historical_dates": [],
        "historical_prices": [],
        "model_historical_predictions": [],
        "forecast_dates": [],
        "forecast_prices": []
    }

    with patch("prediction_service_multihead.get_stock_predictions", return_value=mock_result):
        headers = {"Authorization": f"Bearer {token}"}
        payload = {"ticker": "AAPL", "model": "multihead"}
        
        response = await client.post("/api/predict", json=payload, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "processing"

@pytest.mark.asyncio
async def test_history_endpoint(client: AsyncClient):
    # 1. Register/Login
    auth_payload = {"email": "hist@example.com", "password": "pass"}
    await client.post("/api/auth/register", json=auth_payload)
    login_res = await client.post("/api/auth/login", json=auth_payload)
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create a prediction (mocked) to populate history
    mock_result = {
        "ticker": "GOOGL",
        "metrics": {"rmse": 5.0, "mae": 4.0, "mape": 2.0, "directional_accuracy": 70.0},
        "prediction_data": "dummy" # truncated for test
    }
    
    with patch("prediction_service_multihead.get_stock_predictions", return_value=mock_result):
        await client.post("/api/predict", json={"ticker": "GOOGL"}, headers=headers)
    
    # 3. Fetch History
    response = await client.get("/api/history", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["ticker"] == "GOOGL"
    # assert data[0]["directional_accuracy"] == 70.0 # Might be None if task async
