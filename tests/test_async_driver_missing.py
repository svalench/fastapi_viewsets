"""Regression test for v1.2.1.

When ``async_database_url`` is provided but the corresponding async DB-API
driver (e.g. ``aiosqlite``) is not installed, ``SQLAlchemyAdapter.__init__``
must degrade gracefully to sync-only mode instead of raising
``ModuleNotFoundError`` at construction time.

Regression introduced in v1.2.0 where ``ORMFactory.get_adapter_from_env``
started always passing an explicit ``async_database_url`` to the adapter,
bypassing the existing best-effort ``try/except`` on the URL-conversion path.
"""

from unittest.mock import patch

import pytest

from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter


def _import_error(*_args, **_kwargs):
    raise ModuleNotFoundError("No module named 'aiosqlite'")


def test_explicit_async_url_without_driver_falls_back_to_sync():
    """Adapter must not raise when async driver is missing."""
    with patch(
        "fastapi_viewsets.orm.sqlalchemy_adapter.create_async_engine",
        side_effect=_import_error,
    ):
        adapter = SQLAlchemyAdapter(
            database_url="sqlite:///:memory:",
            async_database_url="sqlite+aiosqlite:///:memory:",
        )

    assert adapter.async_engine is None
    assert adapter.AsyncSessionLocal is None

    # Sync session must keep working.
    session = adapter.get_session()
    assert session is not None
    session.close()

    # Async session must raise a helpful runtime error (not at __init__).
    with pytest.raises(RuntimeError, match="async database driver"):
        adapter.get_async_session()


def test_auto_converted_async_url_without_driver_falls_back_to_sync():
    """Same fallback when ``async_database_url`` is auto-derived."""
    with patch(
        "fastapi_viewsets.orm.sqlalchemy_adapter.create_async_engine",
        side_effect=_import_error,
    ):
        adapter = SQLAlchemyAdapter(database_url="sqlite:///:memory:")

    assert adapter.async_engine is None
    assert adapter.AsyncSessionLocal is None
