"""Utilities for reading serializer (Pydantic schema) configuration.

Provides helpers to extract ``RelatedConfig`` from Pydantic models
so that viewsets can automatically apply the correct eager-loading
strategy (``select_related`` / ``prefetch_related``) without
duplicating configuration.
"""

from typing import Type, List

from pydantic import BaseModel


def get_select_related(response_model: Type[BaseModel]) -> List[str]:
    """Read ``select_related`` from a Pydantic schema's ``RelatedConfig``.

    Args:
        response_model: Pydantic BaseModel subclass that may define
            an inner ``RelatedConfig`` class.

    Returns:
        List of relationship names to load via ``joinedload`` (FK /
        many-to-one relations). Empty list if no config is present.
    """
    cfg = getattr(response_model, "RelatedConfig", None)
    if cfg is None:
        return []
    return list(getattr(cfg, "select_related", []))


def get_prefetch_related(response_model: Type[BaseModel]) -> List[str]:
    """Read ``prefetch_related`` from a Pydantic schema's ``RelatedConfig``.

    Args:
        response_model: Pydantic BaseModel subclass that may define
            an inner ``RelatedConfig`` class.

    Returns:
        List of relationship names to load via ``selectinload`` (one-
        to-many or many-to-many relations). Empty list if no config is
        present.
    """
    cfg = getattr(response_model, "RelatedConfig", None)
    if cfg is None:
        return []
    return list(getattr(cfg, "prefetch_related", []))
