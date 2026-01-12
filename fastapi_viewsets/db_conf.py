import os
from typing import Optional

from dotenv import load_dotenv

from fastapi_viewsets.constants import BASE_DIR
from fastapi_viewsets.orm.factory import ORMFactory
from fastapi_viewsets.orm.base import BaseORMAdapter

load_dotenv(f"{BASE_DIR}.env")

# Get ORM type from environment
ORM_TYPE: str = os.getenv('ORM_TYPE', 'sqlalchemy').lower()

# Get default adapter instance
_default_adapter: Optional[BaseORMAdapter] = None


def get_orm_adapter() -> BaseORMAdapter:
    """Get ORM adapter instance from configuration.
    
    Returns:
        ORM adapter instance based on ORM_TYPE environment variable
        
    Note:
        This function returns a singleton instance. The adapter is created
        based on ORM_TYPE environment variable (default: 'sqlalchemy').
    """
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = ORMFactory.get_adapter_from_env()
    return _default_adapter


# Backward compatibility: SQLAlchemy-specific exports
# These will work only if SQLAlchemy is the selected ORM
try:
    from sqlalchemy import create_engine, Engine
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
    from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
    from sqlalchemy.orm import sessionmaker, scoped_session, Session
    
    SQLALCHEMY_DATABASE_URL: str = os.getenv('SQLALCHEMY_DATABASE_URL') or os.getenv('DATABASE_URL') or f"sqlite:///{BASE_DIR}base.db"
    
    # Synchronous engine and session (for backward compatibility)
    engine: Engine = create_engine(SQLALCHEMY_DATABASE_URL)
    db_session: scoped_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
    SessionLocal: sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base: DeclarativeMeta = declarative_base()
    Base.query = db_session.query_property()
    
    def get_session() -> Session:
        """Get database session (SQLAlchemy).
        
        Returns:
            SQLAlchemy Session instance
            
        Note:
            The session should be closed after use. Consider using context manager.
            This function is for backward compatibility. For new code, use get_orm_adapter().
        """
        return SessionLocal()
    
    # Async engine and session (for backward compatibility)
    def _get_async_database_url() -> str:
        """Convert database URL to async-compatible format."""
        url = SQLALCHEMY_DATABASE_URL
        if url.startswith('sqlite:///'):
            return url.replace('sqlite:///', 'sqlite+aiosqlite:///', 1)
        elif url.startswith('postgresql://'):
            return url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        elif url.startswith('mysql://'):
            return url.replace('mysql://', 'mysql+aiomysql://', 1)
        return url
    
    _async_database_url: Optional[str] = os.getenv('SQLALCHEMY_ASYNC_DATABASE_URL')
    if not _async_database_url:
        _async_database_url = _get_async_database_url()
    
    async_engine: Optional[AsyncEngine] = None
    AsyncSessionLocal: Optional[async_sessionmaker] = None
    
    try:
        async_engine = create_async_engine(_async_database_url, echo=False)
        AsyncSessionLocal = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
    except Exception:
        # If async driver is not installed, async_engine will be None
        pass
    
    def get_async_session() -> AsyncSession:
        """Get async database session (SQLAlchemy).
        
        Returns:
            SQLAlchemy AsyncSession instance
            
        Note:
            The session should be closed after use. Consider using context manager.
            This function is for backward compatibility. For new code, use get_orm_adapter().
            
        Raises:
            RuntimeError: If async engine is not available (async driver not installed)
        """
        if AsyncSessionLocal is None:
            raise RuntimeError(
                "Async session is not available. "
                "Please install async database driver: "
                "pip install aiosqlite (for SQLite) or "
                "pip install asyncpg (for PostgreSQL) or "
                "pip install aiomysql (for MySQL)"
            )
        return AsyncSessionLocal()
    
except ImportError:
    # SQLAlchemy not available - backward compatibility exports will fail
    SQLALCHEMY_DATABASE_URL = ""
    engine = None
    db_session = None
    SessionLocal = None
    Base = None
    
    def get_session():
        """Get database session - SQLAlchemy not available."""
        raise ImportError("SQLAlchemy is not installed. Use get_orm_adapter() instead.")
    
    async_engine = None
    AsyncSessionLocal = None
    
    def get_async_session():
        """Get async database session - SQLAlchemy not available."""
        raise ImportError("SQLAlchemy is not installed. Use get_orm_adapter() instead.")
