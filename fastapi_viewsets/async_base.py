"""Asynchronous CRUD viewset for SQLAlchemy 2.x and Tortoise ORM."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_viewsets._compat import model_to_dict
from fastapi_viewsets._register import _RegisterMixin
from fastapi_viewsets.async_utils import (
    create_element,
    delete_element,
    get_element_by_id,
    get_list_queryset,
    update_element,
)
from fastapi_viewsets.constants import ALLOWED_METHODS
from fastapi_viewsets.db_conf import get_orm_adapter
from fastapi_viewsets.orm.base import BaseORMAdapter

# Type variables for generic types
ModelType = TypeVar("ModelType")
ResponseModelType = TypeVar("ResponseModelType", bound=BaseModel)


def _noop_dependency() -> None:
    """Optional-auth placeholder used as a FastAPI dependency."""
    return None


# Backward-compatible alias.
butle = _noop_dependency


class AsyncBaseViewset(_RegisterMixin, APIRouter):
    """Asynchronous CRUD viewset.

    Mirrors :class:`fastapi_viewsets.BaseViewset` but exposes ``async``
    handlers backed by an async-capable ORM adapter (SQLAlchemy
    AsyncSession or Tortoise ORM).
    """

    ALLOWED_METHODS: List[str] = ALLOWED_METHODS

    def __init__(
        self,
        *args,
        allowed_methods: Optional[List[str]] = None,
        endpoint: Optional[str] = None,
        model: Optional[Type[ModelType]] = None,
        db_session: Optional[Callable[[], AsyncSession]] = None,
        response_model: Optional[Type[ResponseModelType]] = None,
        orm_adapter: Optional[BaseORMAdapter] = None,
        **kwargs,
    ):
        """Initialize the async viewset.

        Args:
            allowed_methods: Optional override of the allowed method set.
            endpoint: Base endpoint path, e.g. ``"/user"``.
            model: ORM model class.
            db_session: Async session factory.
            response_model: Pydantic schema for request/response bodies.
            orm_adapter: ORM adapter; resolved from configuration when
                omitted.
            **kwargs: Forwarded to :class:`fastapi.APIRouter`.
        """
        super().__init__(*args, **kwargs)
        self.allowed_methods: Optional[List[str]] = allowed_methods
        self.endpoint: Optional[str] = endpoint
        self.response_model: Optional[Type[ResponseModelType]] = response_model
        self.model: Optional[Type[ModelType]] = model
        self.db_session: Optional[Callable[[], AsyncSession]] = db_session
        self.orm_adapter: Optional[BaseORMAdapter] = orm_adapter or get_orm_adapter()

    # ------------------------------------------------------------------
    # CRUD handlers
    # ------------------------------------------------------------------

    async def list(
        self,
        limit: Optional[int] = 10,
        offset: Optional[int] = 0,
        search: Optional[str] = None,
        token: str = Depends(_noop_dependency),
    ) -> List[ResponseModelType]:
        """List items with ``limit``/``offset`` pagination (async)."""
        return await get_list_queryset(
            self.model,
            db_session=self.db_session,
            limit=limit,
            offset=offset,
            orm_adapter=self.orm_adapter,
        )

    async def get_element(
        self,
        id: Union[int, str],
        token: str = Depends(_noop_dependency),
    ) -> ResponseModelType:
        """Retrieve a single item by ID (async)."""
        if id is None or (isinstance(id, str) and id.strip() == ""):
            from fastapi import HTTPException
            from starlette import status

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Element id cannot be empty",
            )
        return await get_element_by_id(
            self.model,
            db_session=self.db_session,
            id=id,
            orm_adapter=self.orm_adapter,
        )

    async def create_element(
        self,
        item: ResponseModelType = Body(...),
        token: str = Depends(_noop_dependency),
    ) -> ResponseModelType:
        """Create a new item (async)."""
        return await create_element(
            self.model,
            db_session=self.db_session,
            data=model_to_dict(item),
            orm_adapter=self.orm_adapter,
        )

    async def update_element(
        self,
        id: Union[int, str],
        item: ResponseModelType = Body(...),
        token: str = Depends(_noop_dependency),
        partial: bool = False,
    ) -> ResponseModelType:
        """Update an existing item (async).

        ``partial=True`` (used by ``PATCH``) only writes fields the
        client explicitly set.
        """
        return await update_element(
            self.model,
            self.db_session,
            id,
            model_to_dict(item, exclude_unset=partial),
            partial=partial,
            orm_adapter=self.orm_adapter,
        )

    async def delete_element(
        self,
        id: Union[int, str],
        token: str = Depends(_noop_dependency),
    ) -> Dict[str, Union[bool, str]]:
        """Delete an item by ID (async)."""
        result = await delete_element(
            self.model, self.db_session, id, orm_adapter=self.orm_adapter
        )
        if result is True:
            return {"status": True, "text": "successfully deleted"}
        return {"status": False, "text": "deletion failed"}
