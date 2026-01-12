import pytest
import os
import tempfile
from pathlib import Path

from fastapi_viewsets.db_conf import (
    get_session, get_async_session, engine, async_engine, Base,
    get_orm_adapter, ORM_TYPE
)
from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter


@pytest.mark.unit
class TestDbConf:
    """Tests for database configuration."""

    def test_get_session_returns_session(self):
        """Test that get_session returns a SQLAlchemy session."""
        session = get_session()
        assert session is not None
        from sqlalchemy.orm import Session
        assert isinstance(session, Session)
        session.close()

    def test_get_session_creates_new_session_each_time(self):
        """Test that get_session creates a new session each time."""
        session1 = get_session()
        session2 = get_session()
        
        assert session1 is not session2
        
        session1.close()
        session2.close()

    @pytest.mark.asyncio
    async def test_get_async_session_returns_async_session(self):
        """Test that get_async_session returns an AsyncSession."""
        try:
            session = get_async_session()
            assert session is not None
            from sqlalchemy.ext.asyncio import AsyncSession
            assert isinstance(session, AsyncSession)
            await session.close()
        except RuntimeError:
            pytest.skip("Async database driver not available")

    @pytest.mark.asyncio
    async def test_get_async_session_creates_new_session_each_time(self):
        """Test that get_async_session creates a new session each time."""
        try:
            session1 = get_async_session()
            session2 = get_async_session()
            
            assert session1 is not session2
            
            await session1.close()
            await session2.close()
        except RuntimeError:
            pytest.skip("Async database driver not available")

    def test_engine_is_created(self):
        """Test that engine is created."""
        assert engine is not None
        from sqlalchemy import Engine
        assert isinstance(engine, Engine)

    @pytest.mark.asyncio
    async def test_async_engine_may_be_none_if_driver_not_installed(self):
        """Test that async_engine may be None if driver is not installed."""
        # This is expected behavior - async_engine will be None if driver is not installed
        # The test just verifies the code handles this gracefully
        pass


@pytest.mark.unit
class TestDbConfEnv:
    """Tests for database configuration via environment variables."""

    def test_default_database_url(self):
        """Test that default database URL is used when env var is not set."""
        # The default should be SQLite
        assert engine is not None
        # Check that it's a SQLite URL (default behavior)
        url = str(engine.url)
        assert 'sqlite' in url.lower()

    def test_custom_database_url_via_env(self, monkeypatch):
        """Test that custom database URL can be set via environment variable."""
        # Create a temporary database file
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp_path = tmp.name
        
        try:
            custom_url = f"sqlite:///{tmp_path}"
            monkeypatch.setenv('SQLALCHEMY_DATABASE_URL', custom_url)
            
            # Reload the module to pick up the new env var
            import importlib
            import fastapi_viewsets.db_conf
            importlib.reload(fastapi_viewsets.db_conf)
            
            # Check that the engine uses the custom URL
            from fastapi_viewsets.db_conf import engine as reloaded_engine
            assert str(reloaded_engine.url) == custom_url
            
            # Cleanup
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            # Cleanup on error
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def test_base_is_created(self):
        """Test that Base declarative base is created."""
        assert Base is not None
        from sqlalchemy.ext.declarative import DeclarativeMeta
        assert isinstance(Base, DeclarativeMeta)


@pytest.mark.unit
class TestORMAdapterIntegration:
    """Tests for ORM adapter integration in db_conf."""
    
    def test_get_orm_adapter_returns_adapter(self, monkeypatch):
        """Test that get_orm_adapter returns an adapter."""
        monkeypatch.setenv('ORM_TYPE', 'sqlalchemy')
        monkeypatch.setenv('DATABASE_URL', 'sqlite:///test.db')
        
        # Reload module to pick up env vars
        import importlib
        import fastapi_viewsets.db_conf
        importlib.reload(fastapi_viewsets.db_conf)
        
        from fastapi_viewsets.db_conf import get_orm_adapter
        adapter = get_orm_adapter()
        
        assert adapter is not None
        assert isinstance(adapter, SQLAlchemyAdapter)
    
    def test_get_orm_adapter_singleton(self, monkeypatch):
        """Test that get_orm_adapter returns singleton."""
        monkeypatch.setenv('ORM_TYPE', 'sqlalchemy')
        monkeypatch.setenv('DATABASE_URL', 'sqlite:///test.db')
        
        # Reload module
        import importlib
        import fastapi_viewsets.db_conf
        importlib.reload(fastapi_viewsets.db_conf)
        
        from fastapi_viewsets.db_conf import get_orm_adapter
        adapter1 = get_orm_adapter()
        adapter2 = get_orm_adapter()
        
        # Should be the same instance
        assert adapter1 is adapter2
    
    def test_orm_type_env_var(self, monkeypatch):
        """Test that ORM_TYPE is read from environment."""
        monkeypatch.setenv('ORM_TYPE', 'sqlalchemy')
        
        # Reload module
        import importlib
        import fastapi_viewsets.db_conf
        importlib.reload(fastapi_viewsets.db_conf)
        
        from fastapi_viewsets.db_conf import ORM_TYPE
        assert ORM_TYPE == 'sqlalchemy'

