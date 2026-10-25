"""SQLAlchemy ORM adapter implementation."""

from typing import Optional, Dict, Any, Tuple, Union, Type, TypeVar, List, Callable
from fastapi import HTTPException
from starlette import status
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy import select, or_
from sqlalchemy.orm import joinedload, selectinload

from fastapi_viewsets._compat import to_async_database_url
from fastapi_viewsets.orm.base import BaseORMAdapter, ModelType
from fastapi_viewsets.soft_delete import SoftDeleteConfig

try:
    from sqlalchemy import create_engine, Engine
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker
    from sqlalchemy.orm import sessionmaker, scoped_session
    from sqlalchemy.ext.declarative import declarative_base
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


class SQLAlchemyAdapter(BaseORMAdapter):
    """SQLAlchemy ORM adapter implementation."""
    
    supports_soft_delete = True
    supports_nested = True

    def __init__(
        self,
        database_url: str,
        async_database_url: Optional[str] = None,
        engine: Optional[Engine] = None,
        async_engine: Optional[AsyncEngine] = None,
        base: Optional[DeclarativeMeta] = None
    ):
        """Initialize SQLAlchemy adapter.
        
        Args:
            database_url: Database connection URL for synchronous operations
            async_database_url: Database connection URL for async operations (optional)
            engine: Pre-configured SQLAlchemy engine (optional)
            async_engine: Pre-configured async SQLAlchemy engine (optional)
            base: SQLAlchemy declarative base (optional)
        """
        if not SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "SQLAlchemy is not installed. Please install it with: pip install SQLAlchemy"
            )
        
        self.database_url = database_url
        
        # Setup synchronous engine
        if engine:
            self.engine = engine
        else:
            self.engine = create_engine(database_url)
        
        # Setup synchronous session
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db_session = scoped_session(self.SessionLocal)
        
        # Setup base class
        if base:
            self.Base = base
        else:
            self.Base = declarative_base()
        
        self.Base.query = self.db_session.query_property()
        
        # Setup async engine and session.
        #
        # The async engine is best-effort: if the matching async DB-API
        # driver (aiosqlite, asyncpg, aiomysql, ...) is not installed we
        # fall back to ``async_engine = None`` so that purely synchronous
        # usage still works. The error is re-raised lazily from
        # :meth:`get_async_session` with installation hints.
        if async_engine:
            self.async_engine = async_engine
        else:
            async_url = async_database_url or self._get_async_database_url()
            try:
                self.async_engine = create_async_engine(async_url, echo=False)
            except Exception:
                # Missing async DB-API driver (aiosqlite/asyncpg/aiomysql),
                # or no async dialect for this URL — degrade to sync-only mode.
                # The error is re-raised lazily from ``get_async_session``.
                self.async_engine = None

        if self.async_engine:
            self.AsyncSessionLocal = async_sessionmaker(
                self.async_engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
        else:
            self.AsyncSessionLocal = None
    
    def _get_async_database_url(self) -> str:
        """Convert database URL to async-compatible format."""
        return to_async_database_url(self.database_url)
    
    def get_session(self) -> Session:
        """Get synchronous database session."""
        return self.SessionLocal()
    
    def get_async_session(self) -> AsyncSession:
        """Get asynchronous database session."""
        if self.AsyncSessionLocal is None:
            raise RuntimeError(
                "Async session is not available. "
                "Please install async database driver: "
                "pip install aiosqlite (for SQLite) or "
                "pip install asyncpg (for PostgreSQL) or "
                "pip install aiomysql (for MySQL)"
            )
        return self.AsyncSessionLocal()
    
    def get_base(self) -> DeclarativeMeta:
        """Get SQLAlchemy declarative base."""
        return self.Base
    
    def _apply_list_clauses(
        self,
        model: Type[ModelType],
        stmt: Any,
        search: Optional[str] = None,
        search_fields: Optional[List[str]] = None,
        ordering: Optional[List[str]] = None,
        filters: Optional[Dict[str, Tuple[str, Any]]] = None,
    ) -> Any:
        """Apply search, ordering and filters to a query or statement.

        Works with both legacy ``Query`` (sync) and 2.0-style ``Select``
        (async) because both support ``.filter()`` and ``.order_by()``.
        """
        if search and search_fields:
            term = f"%{search.strip()}%"
            clauses = [
                getattr(model, field_name).ilike(term)
                for field_name in search_fields
            ]
            if clauses:
                stmt = stmt.filter(or_(*clauses))

        if filters:
            for field_name, (op, value) in filters.items():
                column = getattr(model, field_name)
                if op == "eq":
                    stmt = stmt.filter(column == value)
                elif op == "ne":
                    stmt = stmt.filter(column != value)
                elif op == "gt":
                    stmt = stmt.filter(column > value)
                elif op == "gte":
                    stmt = stmt.filter(column >= value)
                elif op == "lt":
                    stmt = stmt.filter(column < value)
                elif op == "lte":
                    stmt = stmt.filter(column <= value)
                elif op == "contains":
                    stmt = stmt.filter(column.ilike(f"%{value}%"))
                elif op == "in":
                    stmt = stmt.filter(column.in_(value))

        if ordering:
            order_tokens = []
            for token in ordering:
                if token.startswith("-"):
                    order_tokens.append(getattr(model, token[1:]).desc())
                else:
                    order_tokens.append(getattr(model, token).asc())
            if order_tokens:
                stmt = stmt.order_by(*order_tokens)

        return stmt

    def get_list_queryset(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Session],
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
        db = db_session()
        try:
            if limit == 0:
                return []
            
            queryset = self._soft_delete_scope(model, db.query(model), soft_delete)
            queryset = self._scope_query(model, queryset, scope)
            if select_related:
                for rel_name in select_related:
                    queryset = queryset.options(joinedload(getattr(model, rel_name)))
            if prefetch_related:
                for rel_name in prefetch_related:
                    queryset = queryset.options(selectinload(getattr(model, rel_name)))
            queryset = self._apply_list_clauses(
                model, queryset, search, search_fields, ordering, filters
            )
            if limit is not None and limit > 0:
                queryset = queryset.limit(limit)
            if offset:
                queryset = queryset.offset(offset)
            return queryset.all()
        finally:
            db.close()
    
    async def get_list_queryset_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], AsyncSession],
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
        db = db_session()
        try:
            if limit == 0:
                return []
            
            stmt = self._soft_delete_scope(model, select(model), soft_delete)
            stmt = self._scope_query(model, stmt, scope)
            if select_related:
                for rel_name in select_related:
                    stmt = stmt.options(joinedload(getattr(model, rel_name)))
            if prefetch_related:
                for rel_name in prefetch_related:
                    stmt = stmt.options(selectinload(getattr(model, rel_name)))
            stmt = self._apply_list_clauses(
                model, stmt, search, search_fields, ordering, filters
            )
            if limit is not None and limit > 0:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)
            result = await db.execute(stmt)
            return list(result.unique().scalars().all())
        finally:
            await db.close()
    
    def get_element_by_id(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Session],
        id: Union[int, str],
        select_related: Optional[List[str]] = None,
        prefetch_related: Optional[List[str]] = None,
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Get single element by ID from database (synchronous)."""
        db = db_session()
        try:
            queryset = self._soft_delete_scope(model, db.query(model), soft_delete)
            queryset = self._scope_query(model, queryset, scope)
            if select_related:
                for rel_name in select_related:
                    queryset = queryset.options(joinedload(getattr(model, rel_name)))
            if prefetch_related:
                for rel_name in prefetch_related:
                    queryset = queryset.options(selectinload(getattr(model, rel_name)))
            result = queryset.filter(getattr(model, 'id') == id).first()
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Element with id {id} not found"
                )
            return result
        finally:
            db.close()
    
    async def get_element_by_id_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], AsyncSession],
        id: Union[int, str],
        select_related: Optional[List[str]] = None,
        prefetch_related: Optional[List[str]] = None,
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Get single element by ID from database (asynchronous)."""
        db = db_session()
        try:
            stmt = self._soft_delete_scope(model, select(model), soft_delete).where(getattr(model, 'id') == id)
            stmt = self._scope_query(model, stmt, scope)
            if select_related:
                for rel_name in select_related:
                    stmt = stmt.options(joinedload(getattr(model, rel_name)))
            if prefetch_related:
                for rel_name in prefetch_related:
                    stmt = stmt.options(selectinload(getattr(model, rel_name)))
            result = await db.execute(stmt)
            element = result.unique().scalar_one_or_none()
            if not element:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Element with id {id} not found"
                )
            return element
        finally:
            await db.close()
    
    def create_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Session],
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
        db = db_session()
        try:
            # Never pass a NULL primary key explicitly — some backends
            # (e.g. PostgreSQL) reject it instead of autoincrementing.
            pk_cols = {col.name for col in model.__table__.primary_key.columns}
            data = {k: v for k, v in dict(data).items() if not (v is None and k in pk_cols)}

            # Validate required fields
            required_fields = {col.name for col in model.__table__.columns 
                             if not col.nullable and col.name != 'id' and not col.primary_key
                             and col.default is None and col.server_default is None}
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
            
            queryset = model(**data)
            db.add(queryset)
            db.commit()
            db.refresh(queryset)
            return queryset
        except HTTPException:
            db.rollback()
            raise
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Integrity error: a database constraint was violated"
            )
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database error"
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error creating element"
            )
        finally:
            db.close()
    
    async def create_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], AsyncSession],
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
        db = db_session()
        try:
            # Never pass a NULL primary key explicitly — some backends
            # (e.g. PostgreSQL) reject it instead of autoincrementing.
            pk_cols = {col.name for col in model.__table__.primary_key.columns}
            data = {k: v for k, v in dict(data).items() if not (v is None and k in pk_cols)}

            # Validate required fields
            required_fields = {col.name for col in model.__table__.columns 
                             if not col.nullable and col.name != 'id' and not col.primary_key
                             and col.default is None and col.server_default is None}
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
            
            queryset = model(**data)
            db.add(queryset)
            await db.commit()
            await db.refresh(queryset)
            return queryset
        except HTTPException:
            await db.rollback()
            raise
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Integrity error: a database constraint was violated"
            )
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database error"
            )
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error creating element"
            )
        finally:
            await db.close()
    
    def update_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Session],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False,
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Update element in database (synchronous)."""
        db = db_session()
        try:
            query = self._scope_query(model, db.query(model), scope).filter(getattr(model, 'id') == id)
            if scope is not None:
                data = self._scoped_data(model, data, scope)
            if soft_delete is not None:
                query = self._soft_delete_scope(model, query, soft_delete)
                data = soft_delete.update_data(data)
            result = query.first()
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Element with id {id} not found"
                )
            
            # Only write fields explicitly present in the payload and
            # never touch the primary key. PATCH payloads arrive with
            # ``exclude_unset`` applied upstream, so explicit ``null``
            # values are honored (they clear the column); PUT replaces
            # exactly the fields the schema carries and leaves columns
            # absent from the schema untouched.
            pk_cols = {col.name for col in model.__table__.primary_key.columns}
            data = {key: value for key, value in dict(data).items() if key not in pk_cols}
            
            if not data:
                db.refresh(result)
                return result
            
            changed = query.update(data, synchronize_session=False)
            if (soft_delete is not None or scope is not None) and not changed:
                raise HTTPException(status_code=404, detail="Element not found")
            db.commit()
            db.refresh(result)
            return result
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Integrity error: a database constraint was violated"
            )
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database error"
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error updating element"
            )
        finally:
            db.close()
    
    async def update_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], AsyncSession],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False,
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> ModelType:
        """Update element in database (asynchronous)."""
        db = db_session()
        try:
            if soft_delete is not None or scope is not None:
                from sqlalchemy import update

                query = self._soft_delete_scope(model, select(model), soft_delete).where(
                    model.id == id
                )
                query = self._scope_query(model, query, scope)
                if scope is not None:
                    data = self._scoped_data(model, data, scope)
                if soft_delete is not None:
                    data = soft_delete.update_data(data)
                result = (await db.execute(query)).unique().scalar_one_or_none()
            else:
                result = await db.get(model, id)
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Element with id {id} not found"
                )
            
            # Only write fields explicitly present in the payload and
            # never touch the primary key. PATCH payloads arrive with
            # ``exclude_unset`` applied upstream, so explicit ``null``
            # values are honored (they clear the column); PUT replaces
            # exactly the fields the schema carries and leaves columns
            # absent from the schema untouched.
            pk_cols = {col.name for col in model.__table__.primary_key.columns}
            data = {key: value for key, value in dict(data).items() if key not in pk_cols}
            
            if not data:
                await db.refresh(result)
                return result
            
            if soft_delete is not None or scope is not None:
                statement = self._soft_delete_scope(model, update(model), soft_delete).where(
                    model.id == id
                )
                statement = self._scope_query(model, statement, scope)
                changed = await db.execute(
                    statement.values(**data).execution_options(synchronize_session=False)
                )
                if not changed.rowcount:
                    raise HTTPException(status_code=404, detail="Element not found")
            else:
                for key, value in data.items():
                    setattr(result, key, value)
            
            await db.commit()
            await db.refresh(result)
            return result
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Integrity error: a database constraint was violated"
            )
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database error"
            )
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error updating element"
            )
        finally:
            await db.close()
    
    def delete_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Session],
        id: Union[int, str],
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Delete element from database by ID (synchronous)."""
        if soft_delete is not None:
            return self._change_deleted_state(model, db_session, id, soft_delete, restore=False, scope=scope)
        db = db_session()
        try:
            if scope is not None:
                query = self._scope_query(model, db.query(model), scope).filter(model.id == id)
                result = query.with_for_update(of=model).one_or_none()
            else:
                result = db.get(model, id)
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Element with id {id} not found"
                )
            db.delete(result)
            db.commit()
            return True
        except HTTPException:
            db.rollback()
            raise
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database error"
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error deleting element"
            )
        finally:
            db.close()
    
    async def delete_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], AsyncSession],
        id: Union[int, str],
        *,
        soft_delete: Optional[SoftDeleteConfig] = None,
        scope: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Delete element from database by ID (asynchronous)."""
        if soft_delete is not None:
            return await self._change_deleted_state_async(model, db_session, id, soft_delete, restore=False, scope=scope)
        db = db_session()
        try:
            if scope is not None:
                statement = self._scope_query(model, select(model), scope).where(model.id == id)
                result = (await db.execute(statement.with_for_update(of=model))).unique().scalar_one_or_none()
            else:
                result = await db.get(model, id)
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Element with id {id} not found"
                )
            await db.delete(result)
            await db.commit()
            return True
        except HTTPException:
            await db.rollback()
            raise
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database error"
            )
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Error deleting element"
            )
        finally:
            await db.close()
    
    def get_model_columns(self, model: Type[ModelType]) -> Dict[str, Any]:
        """Get model column information."""
        columns = {}
        for col in model.__table__.columns:
            columns[col.name] = {
                'nullable': col.nullable,
                'primary_key': col.primary_key,
                'type': str(col.type)
            }
        return columns

    @staticmethod
    def _soft_delete_scope(model, query, config, *, deleted=False):
        if config is None:
            return query
        column = getattr(model, config.field)
        if config.mode == "timestamp":
            clause = column.is_not(None) if deleted else column.is_(None)
        else:
            clause = column.is_(deleted)
        return query.filter(clause)

    def _change_deleted_state(self, model, db_session, id, config, *, restore, scope=None):
        db = db_session()
        try:
            query = self._soft_delete_scope(model, db.query(model), config, deleted=restore)
            query = self._scope_query(model, query, scope)
            value = config.active_value if restore else config.deleted_value()
            changed = query.filter(model.id == id).update(
                {config.field: value}, synchronize_session=False
            )
            if not changed:
                raise HTTPException(status_code=404, detail="Element not found")
            db.commit()
            return True
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Integrity error: a database constraint was violated",
            ) from exc
        except HTTPException:
            db.rollback()
            raise
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(status_code=400, detail="Database error") from exc
        finally:
            db.close()

    async def _change_deleted_state_async(self, model, db_session, id, config, *, restore, scope=None):
        from sqlalchemy import update

        db = db_session()
        try:
            statement = self._soft_delete_scope(model, update(model), config, deleted=restore)
            statement = self._scope_query(model, statement, scope)
            value = config.active_value if restore else config.deleted_value()
            result = await db.execute(
                statement.where(model.id == id).values(**{config.field: value})
                .execution_options(synchronize_session=False)
            )
            if not result.rowcount:
                raise HTTPException(status_code=404, detail="Element not found")
            await db.commit()
            return True
        except IntegrityError as exc:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Integrity error: a database constraint was violated",
            ) from exc
        except HTTPException:
            await db.rollback()
            raise
        except SQLAlchemyError as exc:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Database error") from exc
        finally:
            await db.close()

    def restore_element(self, model, db_session, id, *, soft_delete: SoftDeleteConfig, scope=None) -> bool:
        return self._change_deleted_state(model, db_session, id, soft_delete, restore=True, scope=scope)

    async def restore_element_async(self, model, db_session, id, *, soft_delete: SoftDeleteConfig, scope=None) -> bool:
        return await self._change_deleted_state_async(model, db_session, id, soft_delete, restore=True, scope=scope)

    @staticmethod
    def _scope_query(model, query, scope):
        for field, value in (scope or {}).items():
            query = query.filter(getattr(model, field) == value)
        return query

    def get_nested_field(self, model, field):
        from sqlalchemy import inspect

        attribute = inspect(model).column_attrs.get(field)
        if attribute is None or len(attribute.columns) != 1 or attribute.columns[0].primary_key:
            raise ValueError("nested foreign key must be an existing non-primary-key field")
        return field, tuple({field, attribute.columns[0].name})

    def get_nested_parent_type(self, model):
        from uuid import UUID
        from sqlalchemy import inspect

        attribute = inspect(model).column_attrs.get("id")
        if (attribute is None or len(attribute.columns) != 1 or not attribute.columns[0].primary_key
                or len(inspect(model).primary_key) != 1):
            raise ValueError("parent model must expose its primary key as 'id'")
        try:
            kind = attribute.columns[0].type.python_type
        except NotImplementedError:
            return str
        return kind if kind in (int, str, UUID) else str

    def validate_nested_parent(self, model, field, parent_model):
        from sqlalchemy import inspect

        column = inspect(model).column_attrs[field].columns[0]
        parent_column = inspect(parent_model).column_attrs["id"].columns[0]
        for reference in column.foreign_keys:
            target = reference.column
            if target.table.fullname != parent_column.table.fullname or target.name != parent_column.name:
                raise ValueError("nested foreign key references a different parent model or key")
