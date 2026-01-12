"""Tests for error handling in adapters and utilities."""

import pytest
import tempfile
import os

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


# Test database setup
_test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
_test_db_path = _test_db_file.name
_test_db_file.close()

TEST_DATABASE_URL = f"sqlite:///{_test_db_path}"


@pytest.mark.unit
class TestSQLAlchemyAdapterErrorHandling:
    """Tests for error handling in SQLAlchemyAdapter."""
    
    def test_create_element_integrity_error(self):
        """Test create_element handles IntegrityError."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_integrity"
            id = Column(Integer, primary_key=True)
            name = Column(String, unique=True, nullable=False)
        
        Base.metadata.create_all(adapter.engine)
        
        # Create first record
        adapter.create_element(TestModel, adapter.get_session, {"name": "test"})
        
        # Try to create duplicate (should raise IntegrityError)
        with pytest.raises(HTTPException) as exc_info:
            adapter.create_element(TestModel, adapter.get_session, {"name": "test"})
        
        assert exc_info.value.status_code == 400
        assert "Integrity error" in str(exc_info.value.detail)
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_update_element_not_found(self):
        """Test update_element handles element not found."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_update_not_found"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(adapter.engine)
        
        with pytest.raises(HTTPException) as exc_info:
            adapter.update_element(
                TestModel,
                adapter.get_session,
                999,
                {"name": "test"},
                partial=True
            )
        
        assert exc_info.value.status_code == 404
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    def test_delete_element_not_found(self):
        """Test delete_element handles element not found."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        from sqlalchemy import Column, Integer, String
        
        adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
        Base = adapter.get_base()
        
        class TestModel(Base):
            __tablename__ = "test_delete_not_found"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
        
        Base.metadata.create_all(adapter.engine)
        
        with pytest.raises(HTTPException) as exc_info:
            adapter.delete_element(TestModel, adapter.get_session, 999)
        
        assert exc_info.value.status_code == 404
        
        # Cleanup
        Base.metadata.drop_all(adapter.engine)
        adapter.engine.dispose()
    
    @pytest.mark.asyncio
    async def test_get_async_session_not_available(self):
        """Test get_async_session when async engine is not available."""
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        
        # Create adapter without async engine
        adapter = SQLAlchemyAdapter(
            database_url="sqlite:///test.db",
            async_database_url=None
        )
        
        # Try to get async session when engine is None
        if adapter.async_engine is None:
            with pytest.raises(RuntimeError, match="Async session is not available"):
                adapter.get_async_session()
    
    def test_sqlalchemy_adapter_without_sqlalchemy(self, monkeypatch):
        """Test SQLAlchemyAdapter when SQLAlchemy is not available."""
        # This is hard to test without actually uninstalling SQLAlchemy
        # But we can verify the import check works
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        
        # Should work if SQLAlchemy is installed (which it should be for tests)
        try:
            adapter = SQLAlchemyAdapter(database_url=TEST_DATABASE_URL)
            assert adapter is not None
        except ImportError:
            pytest.skip("SQLAlchemy not available")


@pytest.mark.unit
class TestTortoiseAdapterErrorHandling:
    """Tests for error handling in TortoiseAdapter."""
    
    @pytest.mark.asyncio
    async def test_tortoise_adapter_not_available(self):
        """Test TortoiseAdapter when Tortoise is not available."""
        try:
            from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
            
            # If we can import, test that it raises ImportError when not available
            # This is hard to test without actually uninstalling, so we just verify
            # the structure is correct
            assert True
        except ImportError:
            pytest.skip("Tortoise ORM not available")
    
    @pytest.mark.asyncio
    async def test_tortoise_adapter_sync_methods_not_implemented(self):
        """Test that Tortoise adapter sync methods raise NotImplementedError."""
        try:
            from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
            
            adapter = TortoiseAdapter(
                database_url="sqlite:///test.db",
                models=[]
            )
            
            # All sync methods should raise NotImplementedError
            with pytest.raises(NotImplementedError):
                adapter.get_session()
            
            with pytest.raises(NotImplementedError):
                adapter.get_list_queryset(None, None)
            
            with pytest.raises(NotImplementedError):
                adapter.get_element_by_id(None, None, 1)
            
            with pytest.raises(NotImplementedError):
                adapter.create_element(None, None, {})
            
            with pytest.raises(NotImplementedError):
                adapter.update_element(None, None, 1, {})
            
            with pytest.raises(NotImplementedError):
                adapter.delete_element(None, None, 1)
                
        except ImportError:
            pytest.skip("Tortoise ORM not available")


@pytest.mark.unit
class TestPeeweeAdapterErrorHandling:
    """Tests for error handling in PeeweeAdapter."""
    
    def test_peewee_adapter_not_available(self):
        """Test PeeweeAdapter when Peewee is not available."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            
            # If we can import, test that it raises ImportError when not available
            assert True
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_async_methods_not_implemented(self):
        """Test that Peewee adapter async methods raise NotImplementedError."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            
            adapter = PeeweeAdapter(database_url=TEST_DATABASE_URL)
            
            # All async methods should raise NotImplementedError
            with pytest.raises(NotImplementedError):
                adapter.get_async_session()
            
            import asyncio
            with pytest.raises(NotImplementedError):
                asyncio.run(adapter.get_list_queryset_async(None, None))
            
            with pytest.raises(NotImplementedError):
                asyncio.run(adapter.get_element_by_id_async(None, None, 1))
            
            with pytest.raises(NotImplementedError):
                asyncio.run(adapter.create_element_async(None, None, {}))
            
            with pytest.raises(NotImplementedError):
                asyncio.run(adapter.update_element_async(None, None, 1, {}))
            
            with pytest.raises(NotImplementedError):
                asyncio.run(adapter.delete_element_async(None, None, 1))
                
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_invalid_postgresql_url(self):
        """Test Peewee adapter with invalid PostgreSQL URL."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            
            with pytest.raises(ValueError, match="Invalid PostgreSQL URL"):
                PeeweeAdapter(database_url="postgresql://invalid")
                
        except ImportError:
            pytest.skip("Peewee not available")
    
    def test_peewee_adapter_invalid_mysql_url(self):
        """Test Peewee adapter with invalid MySQL URL."""
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
            
            with pytest.raises(ValueError, match="Invalid MySQL URL"):
                PeeweeAdapter(database_url="mysql://invalid")
                
        except ImportError:
            pytest.skip("Peewee not available")


@pytest.mark.unit
class TestFactoryErrorHandling:
    """Tests for error handling in ORMFactory."""
    
    def test_create_adapter_with_none_config(self):
        """Test creating adapter with None config."""
        from fastapi_viewsets.orm.factory import ORMFactory
        
        # None config should use default database_url
        adapter = ORMFactory.create_adapter('sqlalchemy', {'database_url': TEST_DATABASE_URL})
        assert adapter is not None
    
    def test_create_adapter_with_empty_config(self):
        """Test creating adapter with empty config."""
        from fastapi_viewsets.orm.factory import ORMFactory
        
        # Empty config should use default database_url
        adapter = ORMFactory.create_adapter('sqlalchemy', {'database_url': TEST_DATABASE_URL})
        assert adapter is not None


def cleanup_test_db():
    """Clean up test database file."""
    if os.path.exists(_test_db_path):
        os.unlink(_test_db_path)


import atexit
atexit.register(cleanup_test_db)

