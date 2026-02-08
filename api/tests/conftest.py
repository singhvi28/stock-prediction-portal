import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport
import sys
import os

# Add api directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from httpx import AsyncClient, ASGITransport
import sys

# Add api directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_DB_FILE = "test.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

# Set env to sqlite for tests so db.py picks JSON instead of JSONB
os.environ["DATABASE_URL"] = TEST_DB_URL

from main import app
from db import Base, get_db
from worker import celery_app

# Configure Celery for testing
celery_app.conf.update(
    broker_url='memory://',
    result_backend='cache+memory://',
    task_always_eager=True,
    task_eager_propagates=True,
)

engine = create_async_engine(
    TEST_DB_URL, 
    connect_args={"check_same_thread": False}, 
)
TestingSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)

@pytest.fixture(scope="function")
async def db_session():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session
    
    # Drop tables and remove file
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except:
            pass

@pytest.fixture(scope="function")
async def client(db_session):
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    
    app.dependency_overrides.clear()
