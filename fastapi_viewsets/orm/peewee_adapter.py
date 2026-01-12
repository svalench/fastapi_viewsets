"""Peewee ORM adapter implementation."""

from typing import Optional, Dict, Any, Union, Type, TypeVar, List, Callable
from fastapi import HTTPException
from starlette import status

from fastapi_viewsets.orm.base import BaseORMAdapter, ModelType

try:
    from peewee import Model, Database, DoesNotExist, IntegrityError as PeeweeIntegrityError
    PEEWEE_AVAILABLE = True
except ImportError:
    PEEWEE_AVAILABLE = False
    Model = None


class PeeweeAdapter(BaseORMAdapter):
    """Peewee ORM adapter implementation."""
    
    def __init__(
        self,
        database_url: str,
        database: Optional[Database] = None
    ):
        """Initialize Peewee adapter.
        
        Args:
            database_url: Database connection URL
            database: Pre-configured Peewee database instance (optional)
        """
        if not PEEWEE_AVAILABLE:
            raise ImportError(
                "Peewee is not installed. Please install it with: pip install peewee"
            )
        
        self.database_url = database_url
        self.database = database
        self._parse_database_url()
    
    def _parse_database_url(self):
        """Parse database URL and create Peewee database instance."""
        if self.database:
            return
        
        # Parse database URL
        if self.database_url.startswith('sqlite:///'):
            from peewee import SqliteDatabase
            db_path = self.database_url.replace('sqlite:///', '')
            self.database = SqliteDatabase(db_path)
        elif self.database_url.startswith('postgresql://') or self.database_url.startswith('postgres://'):
            from playhouse.postgres_ext import PostgresqlDatabase
            # Parse postgresql://user:password@host:port/database
            import re
            match = re.match(r'postgres(ql)?://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', self.database_url)
            if match:
                user, password, host, port, database = match.groups()[1:]
                self.database = PostgresqlDatabase(database, user=user, password=password, host=host, port=int(port))
            else:
                raise ValueError(f"Invalid PostgreSQL URL format: {self.database_url}")
        elif self.database_url.startswith('mysql://'):
            from peewee import MySQLDatabase
            import re
            match = re.match(r'mysql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', self.database_url)
            if match:
                user, password, host, port, database = match.groups()
                self.database = MySQLDatabase(database, user=user, password=password, host=host, port=int(port))
            else:
                raise ValueError(f"Invalid MySQL URL format: {self.database_url}")
        else:
            raise ValueError(f"Unsupported database URL: {self.database_url}")
    
    def get_session(self):
        """Get synchronous database session.
        
        Returns:
            Peewee database instance (acts as session)
        """
        return self.database
    
    def get_async_session(self):
        """Get asynchronous database session.
        
        Note: Peewee is sync-only, so this raises NotImplementedError.
        """
        raise NotImplementedError(
            "Peewee ORM is sync-only. Use get_session() instead."
        )
    
    def get_base(self) -> Type:
        """Get Peewee base model class."""
        if not PEEWEE_AVAILABLE:
            raise ImportError("Peewee is not installed")
        return Model
    
    def get_list_queryset(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """Get list of elements from database with pagination support (synchronous)."""
        if limit == 0:
            return []
        
        queryset = model.select()
        
        if offset:
            queryset = queryset.offset(offset)
        if limit is not None and limit > 0:
            queryset = queryset.limit(limit)
        
        return list(queryset)
    
    async def get_list_queryset_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """Get list of elements (asynchronous) - not supported by Peewee."""
        raise NotImplementedError("Peewee ORM is sync-only")
    
    def get_element_by_id(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> ModelType:
        """Get single element by ID from database (synchronous)."""
        try:
            return model.get_by_id(id)
        except DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Element with id {id} not found"
            )
    
    async def get_element_by_id_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> ModelType:
        """Get single element by ID (asynchronous) - not supported by Peewee."""
        raise NotImplementedError("Peewee ORM is sync-only")
    
    def create_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        data: Dict[str, Any]
    ) -> ModelType:
        """Create new element in database (synchronous)."""
        try:
            # Validate required fields
            required_fields = set()
            for field_name, field in model._meta.fields.items():
                if field.null is False and field_name != 'id' and not field.primary_key:
                    required_fields.add(field_name)
            
            provided_fields = {k for k, v in data.items() if v is not None}
            missing_fields = required_fields - provided_fields
            if missing_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required fields: {', '.join(missing_fields)}"
                )
            
            instance = model.create(**data)
            return instance
        except PeeweeIntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Integrity error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error creating element: {str(e)}"
            )
    
    async def create_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        data: Dict[str, Any]
    ) -> ModelType:
        """Create new element (asynchronous) - not supported by Peewee."""
        raise NotImplementedError("Peewee ORM is sync-only")
    
    def update_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False
    ) -> ModelType:
        """Update element in database (synchronous)."""
        try:
            instance = model.get_by_id(id)
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
            all_fields = set(model._meta.fields.keys()) - {'id'}
            data = {col: data.get(col, None) for col in all_fields}
        
        if not data:
            return instance
        
        for key, value in data.items():
            setattr(instance, key, value)
        
        instance.save()
        return instance
    
    async def update_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False
    ) -> ModelType:
        """Update element (asynchronous) - not supported by Peewee."""
        raise NotImplementedError("Peewee ORM is sync-only")
    
    def delete_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> bool:
        """Delete element from database by ID (synchronous)."""
        try:
            instance = model.get_by_id(id)
            instance.delete_instance()
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
    
    async def delete_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> bool:
        """Delete element (asynchronous) - not supported by Peewee."""
        raise NotImplementedError("Peewee ORM is sync-only")
    
    def get_model_columns(self, model: Type[ModelType]) -> Dict[str, Any]:
        """Get model column information."""
        columns = {}
        for field_name, field in model._meta.fields.items():
            columns[field_name] = {
                'nullable': field.null,
                'primary_key': field.primary_key,
                'type': str(type(field).__name__)
            }
        return columns

