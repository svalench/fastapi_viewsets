from fastapi import HTTPException
from starlette import status
from typing import Optional, Dict, Any, Union, Type, TypeVar, List, Callable

from pydantic import BaseModel

from fastapi_viewsets.orm.base import BaseORMAdapter
from fastapi_viewsets.db_conf import get_orm_adapter
from fastapi_viewsets.serializer_utils import get_select_related, get_prefetch_related
from fastapi_viewsets.filtering import get_list_config

# Type variable for ORM models
ModelType = TypeVar('ModelType')


def _resolve_list_options(
    response_model: Optional[Type[BaseModel]],
    search: Optional[str],
    search_fields: Optional[List[str]],
    ordering: Optional[List[str]],
):
    """Fill in declarative ``ListConfig`` defaults for search/ordering."""
    if search_fields is None and search:
        search_fields = get_list_config(response_model).search_fields
    if ordering is None:
        ordering = get_list_config(response_model).ordering or None
    return search_fields, ordering


def _list_extra_kwargs(
    search: Optional[str],
    search_fields: Optional[List[str]],
    ordering: Optional[List[str]],
    filters: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build adapter kwargs for search/ordering/filters.

    Only non-empty values are included so custom ORM adapters that do
    not (yet) accept the new keyword arguments keep working.
    """
    extra: Dict[str, Any] = {}
    if search:
        extra["search"] = search
    if search_fields:
        extra["search_fields"] = search_fields
    if ordering:
        extra["ordering"] = ordering
    if filters:
        extra["filters"] = filters
    return extra


async def get_list_queryset(
    model: Type[ModelType],
    db_session: Callable[[], Any],
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    orm_adapter: Optional[BaseORMAdapter] = None,
    response_model: Optional[Type[BaseModel]] = None,
    select_related: Optional[List[str]] = None,
    prefetch_related: Optional[List[str]] = None,
    search: Optional[str] = None,
    search_fields: Optional[List[str]] = None,
    ordering: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[ModelType]:
    """Get list of elements from database with pagination support (async).
    
    Args:
        model: ORM model class
        db_session: Async database session factory function
        limit: Maximum number of items to return
        offset: Number of items to skip
        orm_adapter: ORM adapter instance (optional, uses default if not provided)
        response_model: Pydantic schema that may define ``RelatedConfig``
            and ``ListConfig``
        select_related: Explicit list of FK relations to join (overrides schema config)
        prefetch_related: Explicit list of collection relations to prefetch (overrides schema config)
        search: Search term for case-insensitive substring matching
        search_fields: Fields to search across (defaults to
            ``ListConfig.search_fields`` from the response schema)
        ordering: Ordering tokens like ``["-name"]`` (defaults to the
            declarative ``ListConfig.ordering`` from the response schema)
        filters: Parsed filter constraints, mapping field name to
            ``(operator, value)`` (see :mod:`fastapi_viewsets.filtering`)
        
    Returns:
        List of model instances
    """
    if orm_adapter is None:
        orm_adapter = get_orm_adapter()
    
    if select_related is None and response_model is not None:
        select_related = get_select_related(response_model)
    if prefetch_related is None and response_model is not None:
        prefetch_related = get_prefetch_related(response_model)
    search_fields, ordering = _resolve_list_options(
        response_model, search, search_fields, ordering
    )
    
    return await orm_adapter.get_list_queryset_async(
        model, db_session, limit, offset,
        select_related=select_related or None,
        prefetch_related=prefetch_related or None,
        **_list_extra_kwargs(search, search_fields, ordering, filters),
    )


async def get_element_by_id(
    model: Type[ModelType],
    db_session: Callable[[], Any],
    id: Union[int, str],
    orm_adapter: Optional[BaseORMAdapter] = None,
    response_model: Optional[Type[BaseModel]] = None,
    select_related: Optional[List[str]] = None,
    prefetch_related: Optional[List[str]] = None,
) -> ModelType:
    """Get single element by ID from database (async).
    
    Args:
        model: ORM model class
        db_session: Async database session factory function
        id: Element ID to retrieve
        orm_adapter: ORM adapter instance (optional, uses default if not provided)
        response_model: Pydantic schema that may define ``RelatedConfig``
        select_related: Explicit list of FK relations to join (overrides schema config)
        prefetch_related: Explicit list of collection relations to prefetch (overrides schema config)
        
    Returns:
        Model instance
        
    Raises:
        HTTPException: If element not found
    """
    if orm_adapter is None:
        orm_adapter = get_orm_adapter()
    
    if select_related is None and response_model is not None:
        select_related = get_select_related(response_model)
    if prefetch_related is None and response_model is not None:
        prefetch_related = get_prefetch_related(response_model)
    
    return await orm_adapter.get_element_by_id_async(
        model, db_session, id,
        select_related=select_related or None,
        prefetch_related=prefetch_related or None,
    )


async def create_element(
    model: Type[ModelType],
    db_session: Callable[[], Any],
    data: Dict[str, Any],
    orm_adapter: Optional[BaseORMAdapter] = None
) -> ModelType:
    """Create new element in database (async).
    
    Args:
        model: ORM model class
        db_session: Async database session factory function
        data: Dictionary with data for new element
        orm_adapter: ORM adapter instance (optional, uses default if not provided)
        
    Returns:
        Created model instance
        
    Raises:
        HTTPException: If creation fails
    """
    if orm_adapter is None:
        orm_adapter = get_orm_adapter()
    
    return await orm_adapter.create_element_async(model, db_session, data)


async def update_element(
    model: Type[ModelType],
    db_session: Callable[[], Any],
    id: Union[int, str],
    data: Dict[str, Any],
    partial: bool = False,
    orm_adapter: Optional[BaseORMAdapter] = None
) -> ModelType:
    """Update element in database (async).
    
    Args:
        model: ORM model class
        db_session: Async database session factory function
        id: Element ID to update
        data: Dictionary with data to update
        partial: If True, update only provided fields (PATCH). If False, replace all fields (PUT).
        orm_adapter: ORM adapter instance (optional, uses default if not provided)
        
    Returns:
        Updated model instance
        
    Raises:
        HTTPException: If update fails or element not found
    """
    if orm_adapter is None:
        orm_adapter = get_orm_adapter()
    
    return await orm_adapter.update_element_async(model, db_session, id, data, partial)


async def delete_element(
    model: Type[ModelType],
    db_session: Callable[[], Any],
    id: Union[int, str],
    orm_adapter: Optional[BaseORMAdapter] = None
) -> bool:
    """Delete element from database by ID (async).
    
    Args:
        model: ORM model class
        db_session: Async database session factory function
        id: Element ID to delete
        orm_adapter: ORM adapter instance (optional, uses default if not provided)
        
    Returns:
        True if deletion was successful
        
    Raises:
        HTTPException: If deletion fails or element not found
    """
    if orm_adapter is None:
        orm_adapter = get_orm_adapter()
    
    return await orm_adapter.delete_element_async(model, db_session, id)

