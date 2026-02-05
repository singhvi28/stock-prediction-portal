import pytest
from httpx import AsyncClient
from unittest.mock import patch

@pytest.mark.asyncio
async def test_register_user(client: AsyncClient):
    payload = {
        "email": "test@example.com",
        "password": "securepassword"
    }
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_register_existing_email(client: AsyncClient):
    payload = {
        "email": "duplicate@example.com",
        "password": "securepassword"
    }
    # Register once
    await client.post("/api/auth/register", json=payload)
    
    # Register again
    response = await client.post("/api/auth/register", json=payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    # Setup
    payload = {
        "email": "login@example.com",
        "password": "securepassword"
    }
    await client.post("/api/auth/register", json=payload)
    
    # Login
    response = await client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data

@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    # Setup
    payload = {
        "email": "wrongpass@example.com",
        "password": "securepassword"
    }
    await client.post("/api/auth/register", json=payload)
    
    # Login with wrong password
    bad_payload = {
        "email": "wrongpass@example.com",
        "password": "wrongpassword"
    }
    response = await client.post("/api/auth/login", json=bad_payload)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_forgot_password(client: AsyncClient):
    # Setup
    payload = {
        "email": "forgot@example.com",
        "password": "securepassword"
    }
    reg_response = await client.post("/api/auth/register", json=payload)
    assert reg_response.status_code == 200, f"Registration failed: {reg_response.text}"
    
    # Request Reset with mocked email
    with patch("main.send_email") as mock_email:
        response = await client.post("/api/auth/forgot-password", json={"email": "forgot@example.com"})
        assert response.status_code == 200
        mock_email.assert_called_once()
