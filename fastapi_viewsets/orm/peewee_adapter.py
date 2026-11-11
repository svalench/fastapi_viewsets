"""Peewee ORM adapter implementation."""

from typing import Optional, Dict, Any, Tuple, Union, Type, TypeVar, List, Callable, TYPE_CHECKING
from fastapi import HTTPException
from starlette import status

from fastapi_viewsets.orm.base import BaseORMAdapter, ModelType
from fastapi_viewsets.soft_delete import SoftDeleteConfig

if TYPE_CHECKING:
    from peewee import Database

try:
    from peewee import Model, Database, DoesNotExist, IntegrityError as PeeweeIntegrityError
    PEEWEE_AVAILABLE = True
except ImportError:
    PEEWEE_AVAILABLE = False
    Model = None
    Database = None  # type: ignore


class PeeweeAdapter(BaseORMAdapter):
    """Peewee ORM adapter implementation."""
    
    supports_soft_delete = True
    supports_nested = True

    def __init__(
        self,
        database_url: str,
        database: Optional[Any] = None
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
        offset: Optional[int] = None,
        select_related: Optional[List[str]] = None,
        prefetch_related: Optional[List[str]] = None,
        search: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
        ordering: Optional[List[str]] = None,
        filters: Optional[Dict[str, Tuple[str, Any]]] = None,
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> List[ModelType]:
        """Get list of elements from database with pagination support (synchronous)."""
        if limit == 0:
            return []
        
        queryset = self._scope_query(model, model.select(), scope)
        if soft_delete is not None:
            queryset = queryset.where(self._soft_delete_clause(model, soft_delete))
        if select_related:
            for rel_name in select_related:
                related_model = getattr(model, rel_name).rel_model
                queryset = queryset.join(related_model)
        if search and search_fields:
            from peewee import Expression, OP, fn
            term = search.strip()
            clauses = [
                fn.LOWER(getattr(model, field_name)).contains(term.lower())
                for field_name in search_fields
            ]
            if clauses:
                combined = clauses[0]
                for clause in clauses[1:]:
                    combined = combined | clause
                queryset = queryset.where(combined)
        if filters:
            for field_name, (op, value) in filters.items():
                column = getattr(model, field_name)
                if op == "eq":
                    queryset = queryset.where(column == value)
                elif op == "ne":
                    queryset = queryset.where(column != value)
                elif op == "gt":
                    queryset = queryset.where(column > value)
                elif op == "gte":
                    queryset = queryset.where(column >= value)
                elif op == "lt":
                    queryset = queryset.where(column < value)
                elif op == "lte":
                    queryset = queryset.where(column <= value)
                elif op == "contains":
                    queryset = queryset.where(
                        fn.LOWER(column).contains(str(value).lower())
                    )
                elif op == "in":
                    queryset = queryset.where(column << value)
        if ordering:
            order_tokens = []
            for token in ordering:
                if token.startswith("-"):
                    order_tokens.append(getattr(model, token[1:]).desc())
                else:
                    order_tokens.append(getattr(model, token).asc())
            if order_tokens:
                queryset = queryset.order_by(*order_tokens)
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
        id: Union[int, str],
        select_related: Optional[List[str]] = None,
        prefetch_related: Optional[List[str]] = None,
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Get single element by ID from database (synchronous)."""
        try:
            queryset = self._scope_query(model, model.select(), scope)
            if soft_delete is not None:
                queryset = queryset.where(self._soft_delete_clause(model, soft_delete))
            if select_related:
                for rel_name in select_related:
                    related_model = getattr(model, rel_name).rel_model
                    queryset = queryset.join(related_model)
            return queryset.where(model.id == id).get()
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
        data: Dict[str, Any],
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Create new element in database (synchronous)."""
        if scope is not None:
            data = self._scoped_data(model, data, scope, create=True)
        if soft_delete is not None:
            data = soft_delete.create_data(data)
        try:
            # Never pass a NULL primary key explicitly.
            pk_name = getattr(model._meta.primary_key, "name", "id")
            data = {k: v for k, v in dict(data).items() if not (v is None and k == pk_name)}

            # Validate required fields
            required_fields = set()
            for field_name, field in model._meta.fields.items():
                if (field.null is False and field_name != 'id'
                        and not field.primary_key and field.default is None):
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
        except HTTPException:
            raise
        except PeeweeIntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Integrity error: a database constraint was violated"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error creating element"
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
        partial: bool = False,
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Update element in database (synchronous)."""
        try:
            if soft_delete is not None or scope is not None:
                query = self._scope_query(model, model.select(), scope).where(model.id == id)
                if soft_delete is not None:
                    query = query.where(self._soft_delete_clause(model, soft_delete))
                    data = soft_delete.update_data(data)
                if scope is not None:
                    data = self._scoped_data(model, data, scope)
                instance = query.get()
            else:
                instance = model.get_by_id(id)
        except DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Element with id {id} not found"
            )
        
        # Only write fields explicitly present in the payload; never
        # touch the primary key. Explicit ``null`` values are honored.
        pk_name = getattr(model._meta.primary_key, "name", "id")
        data = {key: value for key, value in dict(data).items() if key != pk_name}
        
        if not data:
            return instance
        
        for key, value in data.items():
            setattr(instance, key, value)
        
        try:
            if soft_delete is not None or scope is not None:
                query = self._scope_query(model, model.update(**data), scope).where(model.id == id)
                if soft_delete is not None:
                    query = query.where(self._soft_delete_clause(model, soft_delete))
                changed = query.execute()
                if not changed:
                    raise HTTPException(status_code=404, detail="Element not found")
            else:
                instance.save()
        except PeeweeIntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Integrity error: a database constraint was violated",
            ) from exc
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
        id: Union[int, str],
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Delete element from database by ID (synchronous)."""
        if soft_delete is not None:
            return self._change_deleted_state(model, id, soft_delete, restore=False, scope=scope)
        try:
            if scope is not None:
                instance = self._scope_query(model, model.select(), scope).where(model.id == id).get()
            else:
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
                detail="Error deleting element"
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

    @staticmethod
    def _soft_delete_clause(model, config, *, deleted=False):
        column = getattr(model, config.field)
        if config.mode == "timestamp":
            return column.is_null(not deleted)
        return column == deleted

    def _change_deleted_state(self, model, id, config, *, restore, scope=None):
        try:
            value = config.active_value if restore else config.deleted_value()
            query = self._scope_query(model, model.update(**{config.field: value}), scope)
            changed = query.where(
                model.id == id, self._soft_delete_clause(model, config, deleted=restore)
            ).execute()
            if not changed:
                raise HTTPException(status_code=404, detail="Element not found")
            return True
        except PeeweeIntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Integrity error: a database constraint was violated",
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Database error") from exc

    def restore_element(self, model, db_session, id, *, soft_delete: SoftDeleteConfig, scope=None) -> bool:
        return self._change_deleted_state(model, id, soft_delete, restore=True, scope=scope)

    @staticmethod
    def _scope_query(model, query, scope):
        for field, value in (scope or {}).items():
            query = query.where(getattr(model, field) == value)
        return query

    def discover_user_foreign_keys(self, model, user_model):
        try:
            from peewee import ForeignKeyField
        except ImportError:  # pragma: no cover
            return []

        matches: list[str] = []
        for name, info in model._meta.fields.items():
            if isinstance(info, ForeignKeyField) and not info.primary_key:
                related = getattr(info, "rel_model", None)
                if related is user_model:
                    matches.append(getattr(info, "object_id_name", None) or name)
        return matches

    def get_nested_field(self, model, field):
        for name, info in model._meta.fields.items():
            aliases = tuple({name, info.column_name, getattr(info, "object_id_name", name)})
            if field in aliases:
                if info.primary_key:
                    break
                return name, aliases
        raise ValueError("nested foreign key must be an existing non-primary-key field")

    def validate_nested_parent(self, model, field, parent_model):
        info = model._meta.fields[field]
        related = getattr(info, "rel_model", None)
        if related is not None and related is not parent_model:
            raise ValueError("nested foreign key references a different parent model")
        related_field = getattr(info, "rel_field", None)
        if related_field is not None and related_field.name != "id":
            raise ValueError("nested foreign key must reference the parent's id")
