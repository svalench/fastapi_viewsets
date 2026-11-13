"""Asynchronous CRUD viewset for SQLAlchemy 2.x and Tortoise ORM."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from fastapi import APIRouter, Body, Depends, Query, Request
from pydantic import BaseModel

from fastapi_viewsets._compat import model_to_dict
from fastapi_viewsets._register import _RegisterMixin
from fastapi_viewsets.nested import NestedConfig, _NestedMixin
from fastapi_viewsets.permissions import _PermissionsMixin
from fastapi_viewsets.soft_delete import SoftDeleteConfig
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


class AsyncBaseViewset(_PermissionsMixin, _NestedMixin, _RegisterMixin, APIRouter):
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
        db_session: Optional[Callable[[], Any]] = None,
        response_model: Optional[Type[ResponseModelType]] = None,
        orm_adapter: Optional[BaseORMAdapter] = None,
        soft_delete: Optional[SoftDeleteConfig] = None,
        nested: Optional[NestedConfig] = None,
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
            soft_delete: Optional deletion marker configuration; disabled by default.
            nested: Optional parent lookup and child binding configuration.
            **kwargs: Forwarded to :class:`fastapi.APIRouter`.
        """
        super().__init__(*args, **kwargs)
        self.allowed_methods: Optional[List[str]] = allowed_methods
        self.endpoint: Optional[str] = endpoint
        self.response_model: Optional[Type[ResponseModelType]] = response_model
        self.model: Optional[Type[ModelType]] = model
        self.db_session: Optional[Callable[[], Any]] = db_session
        self.orm_adapter: Optional[BaseORMAdapter] = orm_adapter or get_orm_adapter()
        self.soft_delete = soft_delete
        if soft_delete is not None:
            if not isinstance(soft_delete, SoftDeleteConfig):
                raise TypeError("soft_delete must be a SoftDeleteConfig or None")
            if model is None:
                raise ValueError("soft deletion requires a model")
            self.orm_adapter.validate_soft_delete(model, soft_delete)
        self._configure_nested(nested)
        self._configure_permissions()

    # ------------------------------------------------------------------
    # CRUD handlers
    # ------------------------------------------------------------------

    async def list(
        self,
        limit: int = Query(10, ge=0, le=10000),
        offset: int = Query(0, ge=0),
        search: Optional[str] = None,
        ordering: Optional[str] = None,
        request: Request = None,
        token: str = Depends(_noop_dependency),
    ) -> List[ResponseModelType]:
        """List items with pagination, search, ordering and filters (async).

        Query parameters (behaviour is driven by the response schema's
        ``ListConfig`` — see :mod:`fastapi_viewsets.filtering`):

        * ``limit`` / ``offset`` — pagination.
        * ``search`` — case-insensitive substring match across
          ``ListConfig.search_fields``.
        * ``ordering`` — comma-separated fields, ``-`` prefix for
          descending, validated against ``ListConfig.ordering_fields``.
        * ``<field>`` / ``<field>__<op>`` — exact and comparison filters
          on ``ListConfig.filters`` fields.
        """
        from fastapi_viewsets.filtering import (
            get_list_config,
            parse_filters,
            parse_ordering_param,
        )

        # FastAPI resolves ``Query`` defaults for HTTP calls; direct
        # programmatic calls receive the unresolved ``Query`` object.
        if not isinstance(limit, int):
            limit = 10
        if not isinstance(offset, int):
            offset = 0

        self._check_permissions(request, "LIST")

        config = get_list_config(self.response_model)
        return await get_list_queryset(
            self.model,
            db_session=self.db_session,
            limit=limit,
            offset=offset,
            orm_adapter=self.orm_adapter,
            **self._orm_options(request),
            response_model=self.response_model,
            search=search,
            ordering=parse_ordering_param(
                ordering, config.ordering_fields, config.ordering
            ),
            filters=parse_filters(request.query_params, config.filters)
            if request is not None
            else None,
        )

    async def get_element(
        self,
        id: Union[int, str],
        request: Request = None,
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
        self._check_permissions(request, "GET")
        element = await get_element_by_id(
            self.model,
            db_session=self.db_session,
            id=id,
            orm_adapter=self.orm_adapter,
            **self._orm_options(request),
            response_model=self.response_model,
        )
        self._check_object_permissions(request, "GET", element)
        return element

    async def create_element(
        self,
        item: ResponseModelType = Body(...),
        request: Request = None,
        token: str = Depends(_noop_dependency),
    ) -> ResponseModelType:
        """Create a new item (async)."""
        self._check_permissions(request, "POST")
        return await create_element(
            self.model,
            db_session=self.db_session,
            data=model_to_dict(item),
            orm_adapter=self.orm_adapter,
            **self._create_options(request),
        )

    async def update_element(
        self,
        id: Union[int, str],
        item: ResponseModelType = Body(...),
        request: Request = None,
        token: str = Depends(_noop_dependency),
        partial: bool = False,
    ) -> ResponseModelType:
        """Update an existing item (async).

        ``partial=True`` (used by ``PATCH``) only writes fields the
        client explicitly set.
        """
        action = self._action_from_partial(partial)
        self._check_permissions(request, action)
        existing = await get_element_by_id(
            self.model,
            db_session=self.db_session,
            id=id,
            orm_adapter=self.orm_adapter,
            **self._orm_options(request),
            response_model=self.response_model,
        )
        self._check_object_permissions(request, action, existing)
        return await update_element(
            self.model,
            self.db_session,
            id,
            model_to_dict(item, exclude_unset=partial),
            partial=partial,
            orm_adapter=self.orm_adapter,
            **self._orm_options(request),
        )

    async def delete_element(
        self,
        id: Union[int, str],
        request: Request = None,
        token: str = Depends(_noop_dependency),
    ) -> Dict[str, Union[bool, str]]:
        """Delete an item by ID (async)."""
        self._check_permissions(request, "DELETE")
        existing = await get_element_by_id(
            self.model,
            db_session=self.db_session,
            id=id,
            orm_adapter=self.orm_adapter,
            **self._orm_options(request),
            response_model=self.response_model,
        )
        self._check_object_permissions(request, "DELETE", existing)
        result = await delete_element(
            self.model, self.db_session, id, orm_adapter=self.orm_adapter,
            **self._orm_options(request),
        )
        if result is True:
            return {"status": True, "text": "successfully deleted"}
        return {"status": False, "text": "deletion failed"}

    async def restore_element(
        self,
        id: Union[int, str],
        request: Request = None,
        token: str = Depends(_noop_dependency),
    ) -> Dict[str, Union[bool, str]]:
        """Restore a soft-deleted item; active or missing IDs return 404."""
        if self.soft_delete is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Soft deletion is not enabled")
        self._check_permissions(request, "RESTORE")
        result = await self.orm_adapter.restore_element_async(
            self.model, self.db_session, id, **self._orm_options(request)
        )
        return {
            "status": result,
            "text": "successfully restored" if result else "restoration failed",
        }

    async def resolve_parent(self, request: Request) -> Any:
        """Look up the parent; override to add application-specific permissions."""
        model, session, parent_id, options = self._parent_lookup_args(request)
        parent = await self.orm_adapter.get_element_by_id_async(model, session, parent_id, **options)
        if parent is None:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Parent not found")
        return parent
