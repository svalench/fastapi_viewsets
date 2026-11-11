"""Tortoise ORM adapter implementation."""

from typing import Optional, Dict, Any, Tuple, Union, Type, TypeVar, List, Callable
from fastapi import HTTPException
from starlette import status

from fastapi_viewsets.orm.base import BaseORMAdapter, ModelType
from fastapi_viewsets.soft_delete import SoftDeleteConfig

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
    
    supports_soft_delete = True
    supports_nested = True

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

    async def initialize(self, generate_schemas: bool = False) -> None:
        """Initialize the Tortoise connection pool.

        Call this in your application lifespan to explicitly open the
        connection at startup instead of relying on lazy initialisation.

        Args:
            generate_schemas: If True, call ``Tortoise.generate_schemas(safe=True)``
                after init. Useful for development; use Aerich in production.
        """
        await self._ensure_initialized()
        if generate_schemas:
            await Tortoise.generate_schemas(safe=True)

    async def close(self) -> None:
        """Close all Tortoise connections.

        Call this in your application lifespan shutdown handler.
        """
        await Tortoise.close_connections()
        self._initialized = False
    
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
        """Get list of elements from database with pagination support (asynchronous)."""
        await self._ensure_initialized()
        
        if limit == 0:
            return []
        
        queryset = model.all()
        if scope is not None:
            queryset = queryset.filter(**scope)
        if soft_delete is not None:
            queryset = queryset.filter(**self._soft_delete_filters(soft_delete))
        
        if select_related:
            queryset = queryset.prefetch_related(*select_related)
        if prefetch_related:
            queryset = queryset.prefetch_related(*prefetch_related)
        if search and search_fields:
            try:
                from tortoise.expressions import Q  # tortoise-orm >= 0.24
            except ImportError:  # pragma: no cover - older releases
                from tortoise.query_utils import Q  # type: ignore
            conditions = [
                Q(**{f"{field_name}__icontains": search.strip()})
                for field_name in search_fields
            ]
            if conditions:
                combined = conditions[0]
                for condition in conditions[1:]:
                    combined = combined | condition
                queryset = queryset.filter(combined)
        if filters:
            # Tortoise lookup names map 1:1 to our operators; only "eq"
            # and "ne" need translation.
            kwargs: Dict[str, Any] = {}
            for field_name, (op, value) in filters.items():
                if op == "eq":
                    kwargs[field_name] = value
                elif op == "ne":
                    kwargs[f"{field_name}__not"] = value
                else:
                    kwargs[f"{field_name}__{op}"] = value
            if kwargs:
                queryset = queryset.filter(**kwargs)
        if ordering:
            queryset = queryset.order_by(*ordering)
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
        id: Union[int, str],
        select_related: Optional[List[str]] = None,
        prefetch_related: Optional[List[str]] = None,
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Get single element by ID from database (asynchronous)."""
        await self._ensure_initialized()
        
        try:
            queryset = model.filter(id=id)
            if scope is not None:
                queryset = queryset.filter(**scope)
            if soft_delete is not None:
                queryset = queryset.filter(**self._soft_delete_filters(soft_delete))
            if select_related:
                queryset = queryset.prefetch_related(*select_related)
            if prefetch_related:
                queryset = queryset.prefetch_related(*prefetch_related)
            instance = await queryset.first()
            if (soft_delete is not None or scope is not None) and instance is None:
                raise HTTPException(status_code=404, detail="Element not found")
            return instance
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
        data: Dict[str, Any],
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Create new element in database (asynchronous)."""
        if scope is not None:
            data = self._scoped_data(model, data, scope, create=True)
        if soft_delete is not None:
            data = soft_delete.create_data(data)
        await self._ensure_initialized()
        
        try:
            # Never pass a NULL primary key explicitly — Tortoise
            # rejects ``id=None`` instead of autoincrementing.
            pk_attr = getattr(model._meta, "pk_attr", "id")
            data = {k: v for k, v in dict(data).items() if not (v is None and k == pk_attr)}

            # Validate required fields
            required_fields = set()
            for field_name, field in model._meta.fields_map.items():
                if (field.required and field_name != 'id' and not field.generated
                        and getattr(field, "has_db_field", True)):
                    required_fields.add(field_name)
            
            provided_fields = {k for k, v in data.items() if v is not None}
            if scope is not None:
                for field in scope:
                    _, aliases = self.get_nested_field(model, field)
                    provided_fields.update(aliases)
            missing_fields = required_fields - provided_fields
            if missing_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required fields: {', '.join(missing_fields)}"
                )
            
            instance = await model.create(**data)
            return instance
        except HTTPException:
            raise
        except TortoiseIntegrityError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Integrity error: a database constraint was violated"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error creating element"
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
        partial: bool = False,
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Update element in database (asynchronous)."""
        await self._ensure_initialized()
        
        try:
            if soft_delete is not None or scope is not None:
                query = model.filter(**(scope or {}))
                if soft_delete is not None:
                    query = query.filter(**self._soft_delete_filters(soft_delete))
                    data = soft_delete.update_data(data)
                if scope is not None:
                    data = self._scoped_data(model, data, scope)
                instance = await query.get(id=id)
            else:
                instance = await model.get(id=id)
        except DoesNotExist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Element with id {id} not found"
            )
        
        # Only write fields explicitly present in the payload; never
        # touch the primary key. Explicit ``null`` values are honored.
        pk_attr = getattr(model._meta, "pk_attr", "id")
        data = {key: value for key, value in dict(data).items() if key != pk_attr}
        
        if not data:
            return instance
        
        for key, value in data.items():
            setattr(instance, key, value)
        
        try:
            if soft_delete is not None or scope is not None:
                query = model.filter(id=id, **(scope or {}))
                if soft_delete is not None:
                    query = query.filter(**self._soft_delete_filters(soft_delete))
                changed = await query.update(**data)
                if not changed:
                    raise HTTPException(status_code=404, detail="Element not found")
            else:
                await instance.save()
        except TortoiseIntegrityError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Integrity error: a database constraint was violated",
            ) from exc
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
        id: Union[int, str],
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Delete element from database by ID (asynchronous)."""
        if soft_delete is not None:
            return await self._change_deleted_state(model, id, soft_delete, restore=False, scope=scope)
        await self._ensure_initialized()
        
        try:
            if scope is not None:
                instance = await model.filter(**scope).get(id=id)
            else:
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
                detail="Error deleting element"
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

    @staticmethod
    def _soft_delete_filters(config, *, deleted=False):
        if config.mode == "timestamp":
            return {f"{config.field}__isnull": not deleted}
        return {config.field: deleted}

    async def _change_deleted_state(self, model, id, config, *, restore, scope=None):
        await self._ensure_initialized()
        try:
            value = config.active_value if restore else config.deleted_value()
            query = model.filter(id=id, **(scope or {})).filter(**self._soft_delete_filters(config, deleted=restore))
            changed = await query.update(
                **{config.field: value}
            )
            if not changed:
                raise HTTPException(status_code=404, detail="Element not found")
            return True
        except TortoiseIntegrityError as exc:
            raise HTTPException(
                status_code=409,
                detail="Integrity error: a database constraint was violated",
            ) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Database error") from exc

    async def restore_element_async(self, model, db_session, id, *, soft_delete: SoftDeleteConfig, scope=None) -> bool:
        return await self._change_deleted_state(model, id, soft_delete, restore=True, scope=scope)

    def get_nested_field(self, model, field):
        from tortoise.fields.relational import ForeignKeyFieldInstance

        for name, info in model._meta.fields_map.items():
            if isinstance(info, ForeignKeyFieldInstance):
                canonical = f"{name}_id"
                aliases = tuple({name, canonical, info.source_field} - {None})
                if field in aliases:
                    if info.pk:
                        break
                    return canonical, aliases
        return super().get_nested_field(model, field)

    def discover_user_foreign_keys(self, model, user_model):
        from tortoise.fields.relational import ForeignKeyFieldInstance

        user_labels = {
            user_model.__name__,
            f"{user_model.__module__}.{user_model.__name__}",
            f"models.{user_model.__name__}",
        }
        matches: list[str] = []
        for name, info in model._meta.fields_map.items():
            if isinstance(info, ForeignKeyFieldInstance) and not info.pk:
                related = info.related_model
                target = getattr(info, "model_name", None)
                if related is user_model or (related is None and target in user_labels):
                    matches.append(f"{name}_id")
        return matches

    def validate_nested_parent(self, model, field, parent_model):
        from tortoise.fields.relational import ForeignKeyFieldInstance

        for name, info in model._meta.fields_map.items():
            if isinstance(info, ForeignKeyFieldInstance) and field == f"{name}_id":
                related = info.related_model
                if ((related is not None and related is not parent_model)
                        or (related is None and info.model_name.rsplit(".", 1)[-1] != parent_model.__name__)):
                    raise ValueError("nested foreign key references a different parent model")
                if info.to_field not in (None, "id"):
                    raise ValueError("nested foreign key must reference the parent's id")
