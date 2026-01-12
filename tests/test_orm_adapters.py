"""Tests for ORM adapters."""

import pytest
import os
import tempfile
from typing import Callable

from fastapi_viewsets.orm.base import BaseORMAdapter
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
    from sqlalchemy.ext.declarative import declarative_base
    
    Base = adapter.get_base()
    
    class TestModel(Base):
        __tablename__ = "test_model"
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        value = Column(Integer, nullable=True)
        active = Column(Boolean, default=True)
    
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


@pytest.mark.unit
class TestSQLAlchemyAdapter:
    """Tests for SQLAlchemyAdapter."""
    
    def test_get_session(self, sqlalchemy_adapter):
        """Test getting synchronous session."""
        session = sqlalchemy_adapter.get_session()
        assert session is not None
        session.close()
    
    def test_get_async_session(self, sqlalchemy_adapter):
        """Test getting asynchronous session."""
        try:
            session = sqlalchemy_adapter.get_async_session()
            assert session is not None
        except RuntimeError:
            pytest.skip("Async driver not available")
    
    def test_get_base(self, sqlalchemy_adapter):
        """Test getting base class."""
        Base = sqlalchemy_adapter.get_base()
        assert Base is not None
    
    def test_get_list_queryset(self, sqlalchemy_adapter):
        """Test getting list of elements."""
        from sqlalchemy import Column, Integer, String
        Base = sqlalchemy_adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_list"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(sqlalchemy_adapter.engine)
        
        # Create test data
        session = sqlalchemy_adapter.get_session()
        try:
            session.add(TestModel(name="test1"))
            session.add(TestModel(name="test2"))
            session.commit()
        finally:
            session.close()
        
        # Test list query
        result = sqlalchemy_adapter.get_list_queryset(
            TestModel,
            sqlalchemy_adapter.get_session,
            limit=10
        )
        
        assert len(result) == 2
        assert result[0].name in ["test1", "test2"]
        
        # Cleanup
        Base.metadata.drop_all(sqlalchemy_adapter.engine)
    
    def test_get_element_by_id(self, sqlalchemy_adapter):
        """Test getting element by ID."""
        from sqlalchemy import Column, Integer, String
        Base = sqlalchemy_adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_get"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(sqlalchemy_adapter.engine)
        
        # Create test data
        session = sqlalchemy_adapter.get_session()
        try:
            obj = TestModel(name="test")
            session.add(obj)
            session.commit()
            obj_id = obj.id
        finally:
            session.close()
        
        # Test get by id
        result = sqlalchemy_adapter.get_element_by_id(
            TestModel,
            sqlalchemy_adapter.get_session,
            obj_id
        )
        
        assert result.id == obj_id
        assert result.name == "test"
        
        # Cleanup
        Base.metadata.drop_all(sqlalchemy_adapter.engine)
    
    def test_create_element(self, sqlalchemy_adapter):
        """Test creating element."""
        from sqlalchemy import Column, Integer, String
        Base = sqlalchemy_adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_create"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(sqlalchemy_adapter.engine)
        
        # Test create
        result = sqlalchemy_adapter.create_element(
            TestModel,
            sqlalchemy_adapter.get_session,
            {"name": "test"}
        )
        
        assert result.id is not None
        assert result.name == "test"
        
        # Cleanup
        Base.metadata.drop_all(sqlalchemy_adapter.engine)
    
    def test_update_element(self, sqlalchemy_adapter):
        """Test updating element."""
        from sqlalchemy import Column, Integer, String
        Base = sqlalchemy_adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_update"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(sqlalchemy_adapter.engine)
        
        # Create test data
        session = sqlalchemy_adapter.get_session()
        try:
            obj = TestModel(name="old")
            session.add(obj)
            session.commit()
            obj_id = obj.id
        finally:
            session.close()
        
        # Test update
        result = sqlalchemy_adapter.update_element(
            TestModel,
            sqlalchemy_adapter.get_session,
            obj_id,
            {"name": "new"},
            partial=True
        )
        
        assert result.name == "new"
        
        # Cleanup
        Base.metadata.drop_all(sqlalchemy_adapter.engine)
    
    def test_delete_element(self, sqlalchemy_adapter):
        """Test deleting element."""
        from sqlalchemy import Column, Integer, String
        Base = sqlalchemy_adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_delete"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(sqlalchemy_adapter.engine)
        
        # Create test data
        session = sqlalchemy_adapter.get_session()
        try:
            obj = TestModel(name="test")
            session.add(obj)
            session.commit()
            obj_id = obj.id
        finally:
            session.close()
        
        # Test delete
        result = sqlalchemy_adapter.delete_element(
            TestModel,
            sqlalchemy_adapter.get_session,
            obj_id
        )
        
        assert result is True
        
        # Verify deletion
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            sqlalchemy_adapter.get_element_by_id(
                TestModel,
                sqlalchemy_adapter.get_session,
                obj_id
            )
        
        # Cleanup
        Base.metadata.drop_all(sqlalchemy_adapter.engine)
    
    @pytest.mark.asyncio
    async def test_get_list_queryset_async(self, sqlalchemy_adapter):
        """Test getting list of elements (async)."""
        try:
            from sqlalchemy import Column, Integer, String
            Base = sqlalchemy_adapter.get_base()
            
            class TestModel(Base):
                __tablename__ = "test_list_async"
                id = Column(Integer, primary_key=True)
                name = Column(String, nullable=False)
            
            import asyncio
            async def setup():
                async with sqlalchemy_adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.create_all)
            
            await setup()
            
            # Create test data
            session = sqlalchemy_adapter.get_async_session()
            try:
                obj1 = TestModel(name="test1")
                obj2 = TestModel(name="test2")
                session.add(obj1)
                session.add(obj2)
                await session.commit()
            finally:
                await session.close()
            
            # Test list query
            result = await sqlalchemy_adapter.get_list_queryset_async(
                TestModel,
                sqlalchemy_adapter.get_async_session,
                limit=10
            )
            
            assert len(result) == 2
            
            # Cleanup
            async def cleanup():
                async with sqlalchemy_adapter.async_engine.begin() as conn:
                    await conn.run_sync(Base.metadata.drop_all)
            await cleanup()
        except RuntimeError:
            pytest.skip("Async driver not available")


@pytest.mark.unit
class TestORMFactory:
    """Tests for ORMFactory."""
    
    def test_register_adapter(self):
        """Test registering an adapter."""
        class TestAdapter(BaseORMAdapter):
            def get_session(self): pass
            def get_async_session(self): pass
            def get_base(self): pass
            def get_list_queryset(self, model, db_session, limit=None, offset=None): pass
            async def get_list_queryset_async(self, model, db_session, limit=None, offset=None): pass
            def get_element_by_id(self, model, db_session, id): pass
            async def get_element_by_id_async(self, model, db_session, id): pass
            def create_element(self, model, db_session, data): pass
            async def create_element_async(self, model, db_session, data): pass
            def update_element(self, model, db_session, id, data, partial=False): pass
            async def update_element_async(self, model, db_session, id, data, partial=False): pass
            def delete_element(self, model, db_session, id): pass
            async def delete_element_async(self, model, db_session, id): pass
            def get_model_columns(self, model): pass
        
        ORMFactory.register_adapter('test', TestAdapter)
        assert 'test' in ORMFactory._adapters
    
    def test_create_sqlalchemy_adapter(self):
        """Test creating SQLAlchemy adapter via factory."""
        adapter = ORMFactory.create_adapter('sqlalchemy', {
            'database_url': TEST_DATABASE_URL
        })
        
        assert isinstance(adapter, SQLAlchemyAdapter)
        assert adapter.database_url == TEST_DATABASE_URL
    
    def test_create_adapter_invalid_type(self):
        """Test creating adapter with invalid type."""
        with pytest.raises(ValueError, match="Unknown ORM type"):
            ORMFactory.create_adapter('invalid', {})
    
    def test_get_adapter_from_env_sqlalchemy(self, monkeypatch):
        """Test getting adapter from environment (SQLAlchemy)."""
        monkeypatch.setenv('ORM_TYPE', 'sqlalchemy')
        monkeypatch.setenv('DATABASE_URL', TEST_DATABASE_URL)
        
        adapter = ORMFactory.get_adapter_from_env()
        
        assert isinstance(adapter, SQLAlchemyAdapter)
        assert adapter.database_url == TEST_DATABASE_URL
    
    def test_get_adapter_from_env_default(self, monkeypatch):
        """Test getting adapter with default (no ORM_TYPE set)."""
        monkeypatch.delenv('ORM_TYPE', raising=False)
        monkeypatch.setenv('DATABASE_URL', TEST_DATABASE_URL)
        
        adapter = ORMFactory.get_adapter_from_env()
        
        assert isinstance(adapter, SQLAlchemyAdapter)
    
    def test_get_default_adapter(self, monkeypatch):
        """Test getting default adapter (singleton)."""
        monkeypatch.setenv('ORM_TYPE', 'sqlalchemy')
        monkeypatch.setenv('DATABASE_URL', TEST_DATABASE_URL)
        
        adapter1 = ORMFactory.get_default_adapter()
        adapter2 = ORMFactory.get_default_adapter()
        
        # Should be the same instance (singleton)
        assert adapter1 is adapter2


def cleanup_test_db():
    """Clean up test database file."""
    if os.path.exists(_test_db_path):
        os.unlink(_test_db_path)


import atexit
atexit.register(cleanup_test_db)

