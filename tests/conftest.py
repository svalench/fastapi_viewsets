import pytest
import os
from typing import Generator, Callable
from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel
from typing import Optional
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Test database setup
# Use file-based SQLite to ensure same database across connections within a test
import tempfile
import atexit
import os

_test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
_test_db_path = _test_db_file.name
_test_db_file.close()

# Clean up test database file on exit
def _cleanup_test_db():
    if os.path.exists(_test_db_path):
        os.unlink(_test_db_path)

atexit.register(_cleanup_test_db)

TEST_DATABASE_URL = f"sqlite:///{_test_db_path}"
TEST_ASYNC_DATABASE_URL = f"sqlite+aiosqlite:///{_test_db_path}"

# Create test base
TestBase = declarative_base()


# Test SQLAlchemy Model
class TestUser(TestBase):
    """Test SQLAlchemy model"""
    __tablename__ = "test_user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
    age = Column(Integer, nullable=True)


# Test Pydantic Schema
class TestUserSchema(BaseModel):
    """Test Pydantic schema - fields are optional for PATCH updates"""
    id: Optional[int] = None
    username: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = True
    age: Optional[int] = None

    class Config:
        orm_mode = True


# Test Pydantic Schema for creation (without id)
class TestUserCreateSchema(BaseModel):
    """Test Pydantic schema for creation"""
    username: str
    email: str
    is_active: Optional[bool] = True
    age: Optional[int] = None


@pytest.fixture(scope="function")
def test_engine():
    """Create test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    # Drop and recreate tables for each test
    TestBase.metadata.drop_all(engine)
    TestBase.metadata.create_all(engine)
    yield engine
    # Clean up after test
    TestBase.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine) -> Generator[Session, None, None]:
    """Create test database session."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def db_session_factory(test_engine) -> Callable[[], Session]:
    """Create database session factory for testing."""
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    return SessionLocal


@pytest.fixture(scope="function")
def test_async_engine():
    """Create test async database engine."""
    try:
        engine = create_async_engine(
            TEST_ASYNC_DATABASE_URL,
            echo=False
        )
        # Create tables
        import asyncio
        async def setup():
            async with engine.begin() as conn:
                await conn.run_sync(TestBase.metadata.drop_all)
                await conn.run_sync(TestBase.metadata.create_all)
        asyncio.run(setup())
        
        yield engine
        
        # Clean up
        async def cleanup():
            async with engine.begin() as conn:
                await conn.run_sync(TestBase.metadata.drop_all)
            await engine.dispose()
        asyncio.run(cleanup())
    except Exception:
        pytest.skip("Async database driver not available")


@pytest.fixture(scope="function")
async def test_async_session(test_async_engine) -> AsyncSession:
    """Create test async database session."""
    async_session_maker = async_sessionmaker(
        test_async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    # Create tables
    async with test_async_engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)
    
    async with async_session_maker() as session:
        yield session
    
    # Drop tables
    async with test_async_engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.drop_all)


@pytest.fixture(scope="function")
def async_db_session_factory(test_async_engine) -> Callable[[], AsyncSession]:
    """Create async database session factory for testing."""
    # Tables are already created by test_async_engine fixture
    async_session_maker = async_sessionmaker(
        test_async_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    return async_session_maker


@pytest.fixture(scope="function")
def test_model():
    """Return test SQLAlchemy model class."""
    return TestUser


@pytest.fixture(scope="function")
def test_schema():
    """Return test Pydantic schema class."""
    return TestUserSchema


@pytest.fixture(scope="function")
def sample_user_data():
    """Return sample user data for testing."""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "is_active": True,
        "age": 25
    }


@pytest.fixture(scope="function")
def sample_users_data():
    """Return multiple sample user data for testing."""
    return [
        {"username": f"user{i}", "email": f"user{i}@example.com", "is_active": True, "age": 20 + i}
        for i in range(10)
    ]


@pytest.fixture(scope="function")
def test_app():
    """Create test FastAPI application."""
    app = FastAPI()
    return app


@pytest.fixture(scope="function")
def test_client(test_app):
    """Create test client for FastAPI application."""
    return TestClient(test_app)

