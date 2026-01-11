import os
from typing import Generator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base, DeclarativeMeta
from sqlalchemy.orm import sessionmaker, scoped_session, Session

from fastapi_viewsets.constants import BASE_DIR

load_dotenv(f"{BASE_DIR}.env")

SQLALCHEMY_DATABASE_URL: str = os.getenv('SQLALCHEMY_DATABASE_URL') or f"sqlite:///{BASE_DIR}base.db"

# Synchronous engine and session
engine: Engine = create_engine(
    SQLALCHEMY_DATABASE_URL
)
db_session: scoped_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))
SessionLocal: sessionmaker = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base: DeclarativeMeta = declarative_base()
Base.query = db_session.query_property()


def get_session() -> Session:
    """Get database session.
    
    Returns:
        SQLAlchemy Session instance
        
    Note:
        The session should be closed after use. Consider using context manager.
    """
    return SessionLocal()


# Async engine and session
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
    """Get async database session.
    
    Returns:
        SQLAlchemy AsyncSession instance
        
    Note:
        The session should be closed after use. Consider using context manager.
        
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
