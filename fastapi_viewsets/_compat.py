"""Compatibility helpers for Pydantic v1/v2 and shared utilities.

This module centralizes small cross-cutting helpers so the rest of the
package can stay focused on routing and ORM logic.
"""

from __future__ import annotations

from typing import Any, Dict


def model_to_dict(item: Any, *, exclude_unset: bool = False) -> Dict[str, Any]:
    """Convert a Pydantic model (v1 or v2) to a plain dict.

    Prefers Pydantic v2 ``model_dump``. Falls back to v1 ``dict`` for
    backward compatibility. Plain dicts and other mappings are returned
    unchanged.

    Args:
        item: Pydantic model instance, mapping, or arbitrary object.
        exclude_unset: When True, only include fields explicitly set by
            the caller. This is required for proper PATCH semantics so
            that unset fields are not overwritten with defaults.

    Returns:
        A plain ``dict`` representation suitable for ORM operations.
    """
    if item is None:
        return {}
    # Pydantic v2
    if hasattr(item, "model_dump"):
        return item.model_dump(exclude_unset=exclude_unset)
    # Pydantic v1
    if hasattr(item, "dict"):
        try:
            return item.dict(exclude_unset=exclude_unset)
        except TypeError:
            return item.dict()
    # Mapping or arbitrary object
    return dict(item)


def to_async_database_url(url: str) -> str:
    """Convert a synchronous SQLAlchemy URL to its async counterpart.

    Mappings:
        sqlite:///       -> sqlite+aiosqlite:///
        postgresql://    -> postgresql+asyncpg://
        mysql://         -> mysql+aiomysql://

    URLs that already include a ``+driver`` component (e.g. ``sqlite+
    aiosqlite://``) are returned unchanged. Unknown schemes are returned
    as-is so the caller can decide how to handle them.

    Args:
        url: Database URL.

    Returns:
        Async-compatible database URL.
    """
    if not url:
        return url
    if "+" in url.split("://", 1)[0]:
        return url
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("mysql://"):
        return url.replace("mysql://", "mysql+aiomysql://", 1)
    return url
