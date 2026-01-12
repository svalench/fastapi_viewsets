"""Tortoise ORM adapter implementation."""

from typing import Optional, Dict, Any, Union, Type, TypeVar, List, Callable
from fastapi import HTTPException
from starlette import status

from fastapi_viewsets.orm.base import BaseORMAdapter, ModelType

try:
    from tortoise import Tortoise
    from tortoise.models import Model
    from tortoise.exceptions import DoesNotExist, IntegrityError as TortoiseIntegrityError
    TORTOISE_AVAILABLE = True
except ImportError:
    TORTOISE_AVAILABLE = False
    Model = None


class TortoiseAdapter(BaseORMAdapter):
    """Tortoise ORM adapter implementation."""
    
    def __init__(
        self,
        database_url: str,
        models: Optional[List[str]] = None,
        app_label: str = "models"
    ):
        """Initialize Tortoise adapter.
        
        Args:
            database_url: Database connection URL
            models: List of model module paths (e.g., ["app.models"])
            app_label: Application label for models
        """
        if not TORTOISE_AVAILABLE:
            raise ImportError(
                "Tortoise ORM is not installed. Please install it with: pip install tortoise-orm"
            )
        
        self.database_url = database_url
        self.models = models or []
        self.app_label = app_label
        self._initialized = False
    
    async def _ensure_initialized(self):
        """Ensure Tortoise is initialized."""
        if not self._initialized:
            db_config = {
                "connections": {
                    "default": self.database_url
                },
                "apps": {
                    self.app_label: {
                        "models": self.models,
                        "default_connection": "default"
                    }
                }
            }
            await Tortoise.init(config=db_config)
            self._initialized = True
    
    def get_session(self):
        """Get synchronous database session.
        
        Note: Tortoise ORM is async-only, so this raises NotImplementedError.
        """
        raise NotImplementedError(
            "Tortoise ORM is async-only. Use get_async_session() instead."
        )
    
    def get_async_session(self):
        """Get asynchronous database session.
        
        Returns:
            Tortoise connection (context manager)
        """
        return Tortoise.get_connection("default")
    
    def get_base(self) -> Type:
        """Get Tortoise ORM base model class."""
        if not TORTOISE_AVAILABLE:
            raise ImportError("Tortoise ORM is not installed")
        return Model
    
    async def get_list_queryset_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """Get list of elements from database with pagination support (asynchronous)."""
        await self._ensure_initialized()
        
        if limit == 0:
            return []
        
        queryset = model.all()
        
        if offset:
            queryset = queryset.offset(offset)
        if limit is not None and limit > 0:
            queryset = queryset.limit(limit)
        
        return await queryset
    
    def get_list_queryset(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """Get list of elements (synchronous) - not supported by Tortoise."""
        raise NotImplementedError("Tortoise ORM is async-only")
    
    async def get_element_by_id_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> ModelType:
        """Get single element by ID from database (asynchronous)."""
        await self._ensure_initialized()
        
        try:
            return await model.get(id=id)
        except DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Element with id {id} not found"
            )
    
    def get_element_by_id(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> ModelType:
        """Get single element by ID (synchronous) - not supported by Tortoise."""
        raise NotImplementedError("Tortoise ORM is async-only")
    
    async def create_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        data: Dict[str, Any]
    ) -> ModelType:
        """Create new element in database (asynchronous)."""
        await self._ensure_initialized()
        
        try:
            # Validate required fields
            required_fields = set()
            for field_name, field in model._meta.fields_map.items():
                if field.required and field_name != 'id' and not field.generated:
                    required_fields.add(field_name)
            
            provided_fields = {k for k, v in data.items() if v is not None}
            missing_fields = required_fields - provided_fields
            if missing_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required fields: {', '.join(missing_fields)}"
                )
            
            instance = await model.create(**data)
            return instance
        except TortoiseIntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Integrity error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error creating element: {str(e)}"
            )
    
    def create_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        data: Dict[str, Any]
    ) -> ModelType:
        """Create new element (synchronous) - not supported by Tortoise."""
        raise NotImplementedError("Tortoise ORM is async-only")
    
    async def update_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False
    ) -> ModelType:
        """Update element in database (asynchronous)."""
        await self._ensure_initialized()
        
        try:
            instance = await model.get(id=id)
        except DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Element with id {id} not found"
            )
        
        if partial:
            # PATCH: update only provided fields, skip None values
            data = {key: value for key, value in dict(data).items() if value is not None}
        else:
            # PUT: replace all fields with provided values, use None for missing fields
            all_fields = set(model._meta.fields_map.keys()) - {'id'}
            data = {col: data.get(col, None) for col in all_fields}
        
        if not data:
            return instance
        
        for key, value in data.items():
            setattr(instance, key, value)
        
        await instance.save()
        return instance
    
    def update_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False
    ) -> ModelType:
        """Update element (synchronous) - not supported by Tortoise."""
        raise NotImplementedError("Tortoise ORM is async-only")
    
    async def delete_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> bool:
        """Delete element from database by ID (asynchronous)."""
        await self._ensure_initialized()
        
        try:
            instance = await model.get(id=id)
            await instance.delete()
            return True
        except DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Element with id {id} not found"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error deleting element: {str(e)}"
            )
    
    def delete_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> bool:
        """Delete element (synchronous) - not supported by Tortoise."""
        raise NotImplementedError("Tortoise ORM is async-only")
    
    def get_model_columns(self, model: Type[ModelType]) -> Dict[str, Any]:
        """Get model column information."""
        columns = {}
        for field_name, field in model._meta.fields_map.items():
            columns[field_name] = {
                'nullable': not field.required,
                'primary_key': field_name == 'id',
                'type': str(type(field).__name__)
            }
        return columns

