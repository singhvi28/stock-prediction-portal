import pytest
import unittest.mock
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

@pytest.fixture(autouse=True)
def mock_tasks_db_session():
    """
    Ensure tasks.py uses a synchronous session for the test database.
    tasks.py code is synchronous, so it needs a sync session, not the async one used by tests.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker, scoped_session
    
    # Use sync sqlite URL
    SYNC_DB_URL = "sqlite:///test.db"
    
    engine = create_engine(SYNC_DB_URL, connect_args={"check_same_thread": False})
    session_factory = sessionmaker(bind=engine)
    ScopedSession = scoped_session(session_factory)
    
    # Patch tasks.db_session with the scoped session registry
    # tasks.py calls db_session() or db_session.method()
    # In tasks.py: db_session = scoped_session(...)
    # It uses db_session.scalar(), db_session.remove()
    # So we patch it with the ScopedSession object itself.
    
    with unittest.mock.patch("tasks.db_session", ScopedSession):
        yield
    
    ScopedSession.remove()
    engine.dispose()
