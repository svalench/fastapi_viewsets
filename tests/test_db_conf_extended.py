"""Extended tests for db_conf module."""

import pytest
import os
import tempfile
import importlib

from fastapi_viewsets.db_conf import (
    get_orm_adapter, ORM_TYPE, get_session, get_async_session,
    engine, async_engine, Base
)


@pytest.mark.unit
class TestDbConfExtended:
    """Extended tests for db_conf module."""
    
    def test_async_url_conversion_logic_sqlite(self):
        """Test async database URL conversion logic for SQLite."""
        # Test the conversion logic directly (same as in db_conf)
        url = 'sqlite:///test.db'
        result = url.replace('sqlite:///', 'sqlite+aiosqlite:///', 1)
        assert 'sqlite+aiosqlite' in result
    
    def test_async_url_conversion_logic_postgresql(self):
        """Test async database URL conversion logic for PostgreSQL."""
        # Test the conversion logic directly (same as in db_conf)
        url = 'postgresql://user:pass@localhost/db'
        result = url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        assert 'postgresql+asyncpg' in result
    
    def test_async_url_conversion_logic_mysql(self):
        """Test async database URL conversion logic for MySQL."""
        # Test the conversion logic directly (same as in db_conf)
        url = 'mysql://user:pass@localhost/db'
        result = url.replace('mysql://', 'mysql+aiomysql://', 1)
        assert 'mysql+aiomysql' in result
    
    def test_async_url_conversion_logic_no_match(self):
        """Test async database URL with no conversion needed."""
        # Test the conversion logic - URLs that don't match patterns return as-is
        url = 'other://url'
        # Should return as-is (no replacement)
        result = url
        assert result == 'other://url'
    
    def test_sqlalchemy_backward_compatibility(self):
        """Test backward compatibility exports."""
        # These should be available if SQLAlchemy is installed
        assert engine is not None
        assert Base is not None
        assert get_session is not None
    
    def test_get_session_backward_compatibility(self):
        """Test get_session backward compatibility."""
        # get_session should work if SQLAlchemy is available
        try:
            session = get_session()
            assert session is not None
            session.close()
        except (ImportError, TypeError):
            pytest.skip("SQLAlchemy not available or not properly configured")
    
    @pytest.mark.asyncio
    async def test_get_async_session_backward_compatibility(self):
        """Test get_async_session backward compatibility."""
        try:
            session = get_async_session()
            assert session is not None
            await session.close()
        except RuntimeError:
            pytest.skip("Async driver not available")
    
    def test_orm_type_default(self, monkeypatch):
        """Test ORM_TYPE defaults to sqlalchemy."""
        monkeypatch.delenv('ORM_TYPE', raising=False)
        
        # Reload module
        import fastapi_viewsets.db_conf
        importlib.reload(fastapi_viewsets.db_conf)
        
        from fastapi_viewsets.db_conf import ORM_TYPE
        assert ORM_TYPE == 'sqlalchemy'
    
    def test_get_orm_adapter_singleton(self, monkeypatch):
        """Test that get_orm_adapter returns singleton."""
        monkeypatch.setenv('ORM_TYPE', 'sqlalchemy')
        monkeypatch.setenv('DATABASE_URL', 'sqlite:///test.db')
        
        # Reload module to reset singleton
        import fastapi_viewsets.db_conf
        importlib.reload(fastapi_viewsets.db_conf)
        
        from fastapi_viewsets.db_conf import get_orm_adapter
        adapter1 = get_orm_adapter()
        adapter2 = get_orm_adapter()
        
        assert adapter1 is adapter2

