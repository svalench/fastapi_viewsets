"""Database configuration helpers.

Historically this module created a synchronous SQLAlchemy engine, an
async engine and a declarative ``Base`` at import time. That created
two problems:

* importing the package failed when an async driver such as
  ``aiosqlite`` was missing;
* SQLAlchemy-specific globals were always loaded even when another ORM
  was selected via ``ORM_TYPE``.

The module now resolves the SQLAlchemy globals lazily — they are
materialized only on first attribute access — so any non-SQLAlchemy
deployment can import the package cleanly. The classic public symbols
(``engine``, ``Base``, ``db_session``, ``get_session`` …) keep working
through ``__getattr__``.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from dotenv import load_dotenv

from fastapi_viewsets._compat import to_async_database_url
from fastapi_viewsets.constants import BASE_DIR
from fastapi_viewsets.orm.base import BaseORMAdapter
from fastapi_viewsets.orm.factory import ORMFactory

load_dotenv(f"{BASE_DIR}.env")

# ORM type selected by configuration.
ORM_TYPE: str = os.getenv("ORM_TYPE", "sqlalchemy").lower()


def get_orm_adapter() -> BaseORMAdapter:
    """Return the configured singleton ORM adapter.

    The factory caches the adapter on its own, so this is a thin
    pass-through kept for backward compatibility.
    """
    return ORMFactory.get_default_adapter()


# ---------------------------------------------------------------------
# SQLAlchemy compatibility surface (lazy)
# ---------------------------------------------------------------------

# Resolved database URL is exposed as a module-level constant for
# backward compatibility. We keep it cheap to compute so importing the
# module does not require SQLAlchemy.
SQLALCHEMY_DATABASE_URL: str = (
    os.getenv("SQLALCHEMY_DATABASE_URL")
    or os.getenv("DATABASE_URL")
    or f"sqlite:///{BASE_DIR}base.db"
)


_SQLA_LAZY_NAMES = {
    "engine",
    "Base",
    "SessionLocal",
    "db_session",
    "get_session",
    "async_engine",
    "AsyncSessionLocal",
    "get_async_session",
}

_sqla_cache: dict = {}


def _build_sqla_globals() -> dict:
    """Lazily build SQLAlchemy engines/sessions on first use."""
    if _sqla_cache:
        return _sqla_cache

    try:
        from sqlalchemy import create_engine
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )
        from sqlalchemy.ext.declarative import declarative_base
        from sqlalchemy.orm import scoped_session, sessionmaker
    except ImportError:  # pragma: no cover - exercised by the fallback
        for name in _SQLA_LAZY_NAMES:
            if name in {"get_session", "get_async_session"}:
                continue
            _sqla_cache[name] = None

        def _missing_session(*_args, **_kwargs):
            raise ImportError(
                "SQLAlchemy is not installed. Use get_orm_adapter() instead."
            )

        _sqla_cache["get_session"] = _missing_session
        _sqla_cache["get_async_session"] = _missing_session
        return _sqla_cache

    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db_session = scoped_session(SessionLocal)
    Base = declarative_base()
    Base.query = db_session.query_property()

    def get_session():
        """Return a synchronous SQLAlchemy session (legacy helper).

        Prefer FastAPI dependency injection with ``yield`` for new
        applications.
        """
        return SessionLocal()

    async_database_url = (
        os.getenv("SQLALCHEMY_ASYNC_DATABASE_URL")
        or to_async_database_url(SQLALCHEMY_DATABASE_URL)
    )

    async_engine: Optional[Any] = None
    AsyncSessionLocal: Optional[Any] = None
    try:
        async_engine = create_async_engine(async_database_url, echo=False)
        AsyncSessionLocal = async_sessionmaker(
            async_engine, class_=AsyncSession, expire_on_commit=False
        )
    except Exception:  # pragma: no cover - depends on driver availability
        async_engine = None
        AsyncSessionLocal = None

    def get_async_session():
        """Return an async SQLAlchemy session (legacy helper)."""
        if AsyncSessionLocal is None:
            raise RuntimeError(
                "Async session is not available. "
                "Please install an async database driver: "
                "pip install aiosqlite (SQLite), asyncpg (PostgreSQL) "
                "or aiomysql (MySQL)."
            )
        return AsyncSessionLocal()

    _sqla_cache.update(
        {
            "engine": engine,
            "SessionLocal": SessionLocal,
            "db_session": db_session,
            "Base": Base,
            "get_session": get_session,
            "async_engine": async_engine,
            "AsyncSessionLocal": AsyncSessionLocal,
            "get_async_session": get_async_session,
        }
    )
    return _sqla_cache


def __getattr__(name: str) -> Any:
    """Resolve SQLAlchemy globals lazily."""
    if name in _SQLA_LAZY_NAMES:
        return _build_sqla_globals()[name]
    raise AttributeError(f"module 'fastapi_viewsets.db_conf' has no attribute {name!r}")


__all__ = [
    "ORM_TYPE",
    "SQLALCHEMY_DATABASE_URL",
    "get_orm_adapter",
    *sorted(_SQLA_LAZY_NAMES),
]
