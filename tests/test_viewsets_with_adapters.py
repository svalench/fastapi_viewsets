"""Tests for viewsets with ORM adapters."""

import pytest
import tempfile
import os
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from fastapi_viewsets import BaseViewset, AsyncBaseViewset
from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
from fastapi_viewsets.orm.factory import ORMFactory


# Test database setup
_test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
_test_db_path = _test_db_file.name
_test_db_file.close()

TEST_DATABASE_URL = f"sqlite:///{_test_db_path}"
TEST_ASYNC_DATABASE_URL = f"sqlite+aiosqlite:///{_test_db_path}"


@pytest.fixture(scope="function")
def sqlalchemy_adapter():
    """Create SQLAlchemy adapter for testing."""
    adapter = SQLAlchemyAdapter(
        database_url=TEST_DATABASE_URL,
        async_database_url=TEST_ASYNC_DATABASE_URL
    )
    
    # Create test table
    from sqlalchemy import Column, Integer, String, Boolean
    Base = adapter.get_base()
    
    class TestUser(Base):
        __tablename__ = "test_user_adapter"
        id = Column(Integer, primary_key=True)
        username = Column(String, unique=True, nullable=False)
        email = Column(String, unique=True, nullable=False)
        is_active = Column(Boolean, default=True)
        age = Column(Integer, nullable=True)
    
    Base.metadata.create_all(adapter.engine)
    
    yield adapter
    
    # Cleanup
    Base.metadata.drop_all(adapter.engine)
    adapter.engine.dispose()
    if adapter.async_engine:
        import asyncio
        async def cleanup():
            await adapter.async_engine.dispose()
        asyncio.run(cleanup())


@pytest.fixture(scope="function")
def test_user_schema():
    """Test Pydantic schema."""
    from pydantic import BaseModel
    from typing import Optional
    
    class TestUserSchema(BaseModel):
        id: Optional[int] = None
        username: Optional[str] = None
        email: Optional[str] = None
        is_active: Optional[bool] = True
        age: Optional[int] = None
        
        class Config:
            orm_mode = True
    
    return TestUserSchema


@pytest.mark.unit
class TestBaseViewsetWithAdapter:
    """Tests for BaseViewset with explicit ORM adapter."""
    
    def test_viewset_with_explicit_adapter(self, sqlalchemy_adapter, test_user_schema):
        """Test that viewset works with explicitly passed adapter."""
        from sqlalchemy import Column, Integer, String, Boolean
        Base = sqlalchemy_adapter.get_base()
        
        class TestUser(Base):
            __tablename__ = "test_user_explicit"
            id = Column(Integer, primary_key=True)
            username = Column(String, unique=True, nullable=False)
            email = Column(String, unique=True, nullable=False)
            is_active = Column(Boolean, default=True)
            age = Column(Integer, nullable=True)
        
        Base.metadata.create_all(sqlalchemy_adapter.engine)
        
        viewset = BaseViewset(
            endpoint='/users',
            model=TestUser,
            response_model=test_user_schema,
            db_session=sqlalchemy_adapter.get_session,
            orm_adapter=sqlalchemy_adapter,
            tags=['Users']
        )
        
        assert viewset.orm_adapter is sqlalchemy_adapter
        assert viewset.model == TestUser
        
        # Test that adapter is used
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "age": 25
        }
        
        result = viewset.create_element(item=test_user_schema(**user_data))
        assert result.id is not None
        assert result.username == "testuser"
        
        # Cleanup
        Base.metadata.drop_all(sqlalchemy_adapter.engine)
    
    def test_viewset_with_default_adapter(self, test_user_schema, monkeypatch):
        """Test that viewset uses default adapter when not explicitly provided."""
        monkeypatch.setenv('ORM_TYPE', 'sqlalchemy')
        monkeypatch.setenv('DATABASE_URL', TEST_DATABASE_URL)
        
        # Reload module
        import importlib
        import fastapi_viewsets.db_conf
        importlib.reload(fastapi_viewsets.db_conf)
        
        from fastapi_viewsets.db_conf import get_orm_adapter
        from sqlalchemy import Column, Integer, String, Boolean
        from fastapi_viewsets.db_conf import Base
        
        class TestUser(Base):
            __tablename__ = "test_user_default"
            id = Column(Integer, primary_key=True)
            username = Column(String, unique=True, nullable=False)
            email = Column(String, unique=True, nullable=False)
            is_active = Column(Boolean, default=True)
            age = Column(Integer, nullable=True)
        
        adapter = get_orm_adapter()
        Base.metadata.create_all(adapter.engine)
        
        viewset = BaseViewset(
            endpoint='/users',
            model=TestUser,
            response_model=test_user_schema,
            db_session=adapter.get_session,
            tags=['Users']
        )
        
        # Should have default adapter
        assert viewset.orm_adapter is not None
        assert isinstance(viewset.orm_adapter, SQLAlchemyAdapter)
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
    
    def test_viewset_crud_with_adapter(self, sqlalchemy_adapter, test_user_schema):
        """Test full CRUD operations with adapter."""
        from sqlalchemy import Column, Integer, String, Boolean
        Base = sqlalchemy_adapter.get_base()
        
        class TestUser(Base):
            __tablename__ = "test_user_crud"
            id = Column(Integer, primary_key=True)
            username = Column(String, unique=True, nullable=False)
            email = Column(String, unique=True, nullable=False)
            is_active = Column(Boolean, default=True)
            age = Column(Integer, nullable=True)
        
        Base.metadata.create_all(sqlalchemy_adapter.engine)
        
        viewset = BaseViewset(
            endpoint='/users',
            model=TestUser,
            response_model=test_user_schema,
            db_session=sqlalchemy_adapter.get_session,
            orm_adapter=sqlalchemy_adapter,
            tags=['Users']
        )
        
        # CREATE
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "is_active": True,
            "age": 25
        }
        created = viewset.create_element(item=test_user_schema(**user_data))
        assert created.id is not None
        user_id = created.id
        
        # READ
        retrieved = viewset.get_element(user_id)
        assert retrieved.id == user_id
        assert retrieved.username == "testuser"
        
        # LIST
        users = viewset.list(limit=10)
        assert len(users) == 1
        assert users[0].id == user_id
        
        # UPDATE (PATCH)
        update_data = {"username": "updateduser"}
        updated = viewset.update_element(id=user_id, item=test_user_schema(**update_data), partial=True)
        assert updated.username == "updateduser"
        assert updated.email == "test@example.com"  # Should remain unchanged
        
        # DELETE
        result = viewset.delete_element(user_id)
        assert result['status'] is True
        
        # Verify deletion
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            viewset.get_element(user_id)
        
        # Cleanup
        Base.metadata.drop_all(sqlalchemy_adapter.engine)


@pytest.mark.asyncio
@pytest.mark.async_test
class TestAsyncBaseViewsetWithAdapter:
    """Tests for AsyncBaseViewset with explicit ORM adapter."""
    
    async def test_async_viewset_with_explicit_adapter(self, sqlalchemy_adapter, test_user_schema):
        """Test that async viewset works with explicitly passed adapter."""
        try:
            from sqlalchemy import Column, Integer, String, Boolean
            Base = sqlalchemy_adapter.get_base()
            
            class TestUser(Base):
                __tablename__ = "test_user_async_explicit"
                id = Column(Integer, primary_key=True)
                username = Column(String, unique=True, nullable=False)
                email = Column(String, unique=True, nullable=False)
                is_active = Column(Boolean, default=True)
                age = Column(Integer, nullable=True)
            
            import asyncio
            async def setup():
                async with sqlalchemy_adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            
            await setup()
            
            viewset = AsyncBaseViewset(
                endpoint='/users',
                model=TestUser,
                response_model=test_user_schema,
                db_session=sqlalchemy_adapter.get_async_session,
                orm_adapter=sqlalchemy_adapter,
                tags=['Users']
            )
            
            assert viewset.orm_adapter is sqlalchemy_adapter
            
            # Test that adapter is used
            user_data = {
                "username": "testuser",
                "email": "test@example.com",
                "is_active": True,
                "age": 25
            }
            
            result = await viewset.create_element(item=test_user_schema(**user_data))
            assert result.id is not None
            assert result.username == "testuser"
            
            # Cleanup
            async def cleanup():
                async with sqlalchemy_adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
            await cleanup()
        except RuntimeError:
            pytest.skip("Async driver not available")
    
    async def test_async_viewset_crud_with_adapter(self, sqlalchemy_adapter, test_user_schema):
        """Test full async CRUD operations with adapter."""
        try:
            from sqlalchemy import Column, Integer, String, Boolean
            Base = sqlalchemy_adapter.get_base()
            
            class TestUser(Base):
                __tablename__ = "test_user_async_crud"
                id = Column(Integer, primary_key=True)
                username = Column(String, unique=True, nullable=False)
                email = Column(String, unique=True, nullable=False)
                is_active = Column(Boolean, default=True)
                age = Column(Integer, nullable=True)
            
            import asyncio
            async def setup():
                async with sqlalchemy_adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            
            await setup()
            
            viewset = AsyncBaseViewset(
                endpoint='/users',
                model=TestUser,
                response_model=test_user_schema,
                db_session=sqlalchemy_adapter.get_async_session,
                orm_adapter=sqlalchemy_adapter,
                tags=['Users']
            )
            
            # CREATE
            user_data = {
                "username": "testuser",
                "email": "test@example.com",
                "is_active": True,
                "age": 25
            }
            created = await viewset.create_element(item=test_user_schema(**user_data))
            assert created.id is not None
            user_id = created.id
            
            # READ
            retrieved = await viewset.get_element(user_id)
            assert retrieved.id == user_id
            assert retrieved.username == "testuser"
            
            # LIST
            users = await viewset.list(limit=10)
            assert len(users) == 1
            assert users[0].id == user_id
            
            # UPDATE (PATCH)
            update_data = {"username": "updateduser"}
            updated = await viewset.update_element(id=user_id, item=test_user_schema(**update_data), partial=True)
            assert updated.username == "updateduser"
            
            # DELETE
            result = await viewset.delete_element(user_id)
            assert result['status'] is True
            
            # Cleanup
            async def cleanup():
                async with sqlalchemy_adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
            await cleanup()
        except RuntimeError:
            pytest.skip("Async driver not available")


def cleanup_test_db():
    """Clean up test database file."""
    if os.path.exists(_test_db_path):
        os.unlink(_test_db_path)


import atexit
atexit.register(cleanup_test_db)

