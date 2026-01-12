"""SQLAlchemy ORM adapter implementation."""

from typing import Optional, Dict, Any, Union, Type, TypeVar, List, Callable
from fastapi import HTTPException
from starlette import status
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import DeclarativeMeta
from sqlalchemy import select

from fastapi_viewsets.orm.base import BaseORMAdapter, ModelType

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
        
        # Setup async engine and session
        if async_engine:
            self.async_engine = async_engine
        elif async_database_url:
            self.async_engine = create_async_engine(async_database_url, echo=False)
        else:
            # Auto-convert sync URL to async
            async_url = self._get_async_database_url()
            try:
                self.async_engine = create_async_engine(async_url, echo=False)
            except Exception:
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
        url = self.database_url
        if url.startswith('sqlite:///'):
            return url.replace('sqlite:///', 'sqlite+aiosqlite:///', 1)
        elif url.startswith('postgresql://'):
            return url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        elif url.startswith('mysql://'):
            return url.replace('mysql://', 'mysql+aiomysql://', 1)
        return url
    
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
    
    def get_list_queryset(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Session],
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """Get list of elements from database with pagination support (synchronous)."""
        db = db_session()
        try:
            if limit == 0:
                return []
            
            queryset = db.query(model)
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
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """Get list of elements from database with pagination support (asynchronous)."""
        db = db_session()
        try:
            if limit == 0:
                return []
            
            stmt = select(model)
            if limit is not None and limit > 0:
                stmt = stmt.limit(limit)
            if offset:
                stmt = stmt.offset(offset)
            result = await db.execute(stmt)
            return list(result.scalars().all())
        finally:
            await db.close()
    
    def get_element_by_id(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Session],
        id: Union[int, str]
    ) -> ModelType:
        """Get single element by ID from database (synchronous)."""
        db = db_session()
        try:
            result = db.query(model).filter(getattr(model, 'id') == id).first()
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
        id: Union[int, str]
    ) -> ModelType:
        """Get single element by ID from database (asynchronous)."""
        db = db_session()
        try:
            stmt = select(model).where(getattr(model, 'id') == id)
            result = await db.execute(stmt)
            element = result.scalar_one_or_none()
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
        data: Dict[str, Any]
    ) -> ModelType:
        """Create new element in database (synchronous)."""
        db = db_session()
        try:
            # Validate required fields
            required_fields = {col.name for col in model.__table__.columns 
                             if not col.nullable and col.name != 'id' and not col.primary_key}
            provided_fields = {k for k, v in data.items() if v is not None}
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Integrity error: {str(e)}"
            )
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database error: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error creating element: {str(e)}"
            )
        finally:
            db.close()
    
    async def create_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], AsyncSession],
        data: Dict[str, Any]
    ) -> ModelType:
        """Create new element in database (asynchronous)."""
        db = db_session()
        try:
            # Validate required fields
            required_fields = {col.name for col in model.__table__.columns 
                             if not col.nullable and col.name != 'id' and not col.primary_key}
            provided_fields = {k for k, v in data.items() if v is not None}
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
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Integrity error: {str(e)}"
            )
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database error: {str(e)}"
            )
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error creating element: {str(e)}"
            )
        finally:
            await db.close()
    
    def update_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Session],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False
    ) -> ModelType:
        """Update element in database (synchronous)."""
        db = db_session()
        try:
            result = db.query(model).filter(getattr(model, 'id') == id).first()
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Element with id {id} not found"
                )
            
            if partial:
                data = {key: value for key, value in dict(data).items() if value is not None}
            else:
                all_columns = {col.name for col in model.__table__.columns if not col.primary_key}
                data = {col: data.get(col, None) for col in all_columns}
            
            if not data:
                db.refresh(result)
                return result
            
            db.query(model).filter(getattr(model, 'id') == id).update(data, synchronize_session=False)
            db.commit()
            db.refresh(result)
            return result
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Integrity error: {str(e)}"
            )
        except SQLAlchemyError as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database error: {str(e)}"
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error updating element: {str(e)}"
            )
        finally:
            db.close()
    
    async def update_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], AsyncSession],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False
    ) -> ModelType:
        """Update element in database (asynchronous)."""
        db = db_session()
        try:
            result = await db.get(model, id)
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Element with id {id} not found"
                )
            
            if partial:
                data = {key: value for key, value in dict(data).items() if value is not None}
            else:
                all_columns = {col.name for col in model.__table__.columns if not col.primary_key}
                data = {col: data.get(col, None) for col in all_columns}
            
            if not data:
                await db.refresh(result)
                return result
            
            for key, value in data.items():
                setattr(result, key, value)
            
            await db.commit()
            await db.refresh(result)
            return result
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Integrity error: {str(e)}"
            )
        except SQLAlchemyError as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Database error: {str(e)}"
            )
        except HTTPException:
            await db.rollback()
            raise
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error updating element: {str(e)}"
            )
        finally:
            await db.close()
    
    def delete_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Session],
        id: Union[int, str]
    ) -> bool:
        """Delete element from database by ID (synchronous)."""
        db = db_session()
        try:
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
                detail=f"Database error: {str(e)}"
            )
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error deleting element: {str(e)}"
            )
        finally:
            db.close()
    
    async def delete_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], AsyncSession],
        id: Union[int, str]
    ) -> bool:
        """Delete element from database by ID (asynchronous)."""
        db = db_session()
        try:
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
                detail=f"Database error: {str(e)}"
            )
        except Exception as e:
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error deleting element: {str(e)}"
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

