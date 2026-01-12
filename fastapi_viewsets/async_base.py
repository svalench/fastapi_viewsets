import functools
from collections.abc import Iterable
from typing import List, Optional, Any, Callable, Type, TypeVar, Union, Dict

from fastapi import APIRouter, Body, Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_viewsets.constants import ALLOWED_METHODS, MAP_METHODS
from fastapi_viewsets.async_utils import (
    get_list_queryset,
    get_element_by_id,
    create_element,
    update_element,
    delete_element
)
from fastapi_viewsets.orm.base import BaseORMAdapter
from fastapi_viewsets.db_conf import get_orm_adapter

# Type variables for generic types
ModelType = TypeVar('ModelType')
ResponseModelType = TypeVar('ResponseModelType', bound=BaseModel)


def butle() -> None:
    """Dummy dependency function for optional authentication."""
    return None


class AsyncBaseViewset(APIRouter):
    """Async base class for Viewset endpoint.
    
    This class provides async CRUD operations for SQLAlchemy models with FastAPI.
    It automatically generates REST endpoints for list, get, create, update, and delete operations.
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
        **kwargs
    ):
        """Initialize AsyncBaseViewset.
        
        Args:
            allowed_methods: List of allowed HTTP methods (optional)
            endpoint: Base endpoint path (e.g., '/user')
            model: ORM model class
            db_session: Async database session factory function
            response_model: Pydantic model for response serialization
            orm_adapter: ORM adapter instance (optional, uses default if not provided)
            **kwargs: Additional arguments passed to APIRouter
        """
        super().__init__(*args, **kwargs)
        self.allowed_methods: Optional[List[str]] = allowed_methods
        self.endpoint: Optional[str] = endpoint
        self.response_model: Optional[Type[ResponseModelType]] = response_model
        self.model: Optional[Type[ModelType]] = model
        self.db_session: Optional[Callable[[], AsyncSession]] = db_session
        self.orm_adapter: Optional[BaseORMAdapter] = orm_adapter or get_orm_adapter()

    def register(
        self,
        methods: Optional[List[str]] = None,
        oauth_protect: Optional[OAuth2PasswordBearer] = None,
        protected_methods: Optional[List[str]] = None
    ) -> None:
        """Register CRUD endpoints.
        
        Args:
            methods: List of methods to register (default: all allowed methods)
            oauth_protect: OAuth2PasswordBearer instance for protected endpoints
            protected_methods: List of methods that require authentication
        """
        if not protected_methods:
            protected_methods = []
        if not methods:
            methods = self.ALLOWED_METHODS
        if not isinstance(methods, Iterable):
            raise ValueError('methods must be List of methods (e.g. ["GET"])')
        
        # Sort methods to register LIST before GET (more specific routes after general ones)
        # This ensures FastAPI can properly route requests - LIST (no params) before GET (with {id})
        # FastAPI requires routes without path parameters to be registered before routes with parameters
        method_order = ['LIST', 'POST', 'GET', 'PUT', 'PATCH', 'DELETE']
        sorted_methods = sorted(methods, key=lambda x: method_order.index(x) if x in method_order else len(method_order))
        
        # Register LIST separately first to ensure it's registered before GET
        list_method = None
        other_methods = []
        for method in sorted_methods:
            if method == 'LIST':
                list_method = method
            else:
                other_methods.append(method)
        
        # Register LIST first if it exists
        if list_method:
            method = list_method
            data_method = MAP_METHODS.get(method)
            if data_method:
                self_method = getattr(self, data_method.get('method'))
                try:
                    self_method.__annotations__['item'] = self.response_model
                except:
                    pass
                old_docstring = self_method.__doc__
                
                if method in protected_methods and oauth_protect:
                    self_method = functools.partial(self_method, token=Depends(oauth_protect))
                    self_method.__doc__ = old_docstring
                route_name = f"{method.lower()}_{self.endpoint.replace('/', '_').strip('_')}"
                self.add_api_route(
                    self.endpoint + data_method.get('path', ''),
                    self_method,
                    response_model=(List[self.response_model] if data_method.get('is_list', False) else self.response_model) if data_method.get('http_method', False) != "DELETE" else None,
                    tags=self.tags,
                    methods=[data_method.get('http_method')],
                    name=route_name,
                )
        
        # Then register all other methods
        for method in other_methods:
            data_method = MAP_METHODS.get(method)
            if not data_method:
                raise ValueError(f'Unknown method: {method}. Allowed methods: {list(MAP_METHODS.keys())}')
            self_method = getattr(self, data_method.get('method'))
            try:
                self_method.__annotations__['item'] = self.response_model
            except:
                pass
            old_docstring = self_method.__doc__
            
            # Handle PUT vs PATCH distinction
            if method == 'PATCH' and data_method.get('method') == 'update_element':
                self_method = functools.partial(self_method, partial=True)
            elif method == 'PUT' and data_method.get('method') == 'update_element':
                self_method = functools.partial(self_method, partial=False)
            
            if method in protected_methods and oauth_protect:
                self_method = functools.partial(self_method, token=Depends(oauth_protect))
                self_method.__doc__ = old_docstring
            # Use name parameter to help FastAPI distinguish routes
            route_name = f"{method.lower()}_{self.endpoint.replace('/', '_').strip('_')}"
            self.add_api_route(
                self.endpoint + data_method.get('path', ''),
                self_method,
                response_model=(List[self.response_model] if data_method.get('is_list', False) else self.response_model) if data_method.get('http_method', False) != "DELETE" else None,
                tags=self.tags,
                methods=[data_method.get('http_method')],
                name=route_name,
            )

    async def list(
        self,
        limit: Optional[int] = 10,
        offset: Optional[int] = 0,
        search: Optional[str] = None,
        token: str = Depends(butle)
    ) -> List[ResponseModelType]:
        """List all elements with pagination support (async).
        
        Args:
            limit: Maximum number of items to return
            offset: Number of items to skip
            search: Search query (not implemented yet)
            token: Authentication token (optional)
            
        Returns:
            List of model instances
        """
        return await get_list_queryset(self.model, db_session=self.db_session, limit=limit, offset=offset, orm_adapter=self.orm_adapter)

    async def get_element(
        self,
        id: Union[int, str],
        token: str = Depends(butle)
    ) -> ResponseModelType:
        """Get single element by ID (async).
        
        Args:
            id: Element ID
            token: Authentication token (optional)
            
        Returns:
            Model instance
            
        Raises:
            HTTPException: If element not found
        """
        # Validate id to prevent conflicts with LIST endpoint
        if id is None or (isinstance(id, str) and id.strip() == ''):
            from fastapi import HTTPException
            from starlette import status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Element id cannot be empty"
            )
        return await get_element_by_id(self.model, db_session=self.db_session, id=id, orm_adapter=self.orm_adapter)

    async def create_element(
        self,
        item: ResponseModelType = Body(...),
        token: str = Depends(butle)
    ) -> ResponseModelType:
        """Create new element (async).
        
        Args:
            item: Pydantic model instance with data for new element
            token: Authentication token (optional)
            
        Returns:
            Created model instance
            
        Raises:
            HTTPException: If creation fails
        """
        return await create_element(self.model, db_session=self.db_session, data=dict(item), orm_adapter=self.orm_adapter)

    async def update_element(
        self,
        id: Union[int, str],
        item: ResponseModelType = Body(...),
        token: str = Depends(butle),
        partial: bool = False
    ) -> ResponseModelType:
        """Update element (async).
        
        Args:
            id: Element ID to update
            item: Pydantic model instance with data to update
            token: Authentication token (optional)
            partial: If True, update only provided fields (PATCH). If False, replace all fields (PUT).
            
        Returns:
            Updated model instance
            
        Raises:
            HTTPException: If update fails or element not found
        """
        return await update_element(self.model, self.db_session, id, dict(item), partial=partial, orm_adapter=self.orm_adapter)

    async def delete_element(
        self,
        id: Union[int, str],
        token: str = Depends(butle)
    ) -> Dict[str, Union[bool, str]]:
        """Delete element by ID (async).
        
        Args:
            id: Element ID to delete
            token: Authentication token (optional)
            
        Returns:
            Dictionary with status and message
            
        Raises:
            HTTPException: If deletion fails or element not found
        """
        result = await delete_element(self.model, self.db_session, id, orm_adapter=self.orm_adapter)
        return {
            'status': True,
            'text': "successfully deleted"
        } if result is True else {
            'status': False,
            'text': "deletion failed"
        }

