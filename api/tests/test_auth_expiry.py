import pytest
from datetime import datetime, timedelta
import jwt
from httpx import AsyncClient
from main import app
from utils import SECRET_KEY, ALGORITHM

@pytest.mark.asyncio
async def test_access_with_expired_token(client: AsyncClient, db_session):
    # 1. Create a token that is already expired
    # We can manually create a JWT with a past 'exp' claim
    expire = datetime.utcnow() - timedelta(minutes=1)
    to_encode = {"sub": "test@example.com", "exp": expire}
    expired_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    # 2. Try to access a protected endpoint
    # /api/auth/verify is a good candidate as it just checks the token
    response = await client.get(
        "/api/auth/verify",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    
    # 3. Verify response is 401 Unauthorized
    assert response.status_code == 401
    assert response.json() == {"detail": "Token has expired"}
