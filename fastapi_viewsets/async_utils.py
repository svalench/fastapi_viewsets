from fastapi import HTTPException
from starlette import status
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any, Union, Type, TypeVar, List, Callable

# Type variable for SQLAlchemy models
ModelType = TypeVar('ModelType')


async def get_list_queryset(
    model: Type[ModelType],
    db_session: Callable[[], AsyncSession],
    limit: Optional[int] = None,
    offset: Optional[int] = None
) -> List[ModelType]:
    """Get list of elements from database with pagination support (async).
    
    Args:
        model: SQLAlchemy model class
        db_session: Async database session factory function
        limit: Maximum number of items to return
        offset: Number of items to skip
        
    Returns:
        List of model instances
    """
    db = db_session()
    try:
        # If limit is 0, return empty list immediately
        if limit == 0:
            return []
        
        from sqlalchemy import select
        stmt = select(model)
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)
        if offset:
            stmt = stmt.offset(offset)
        result = await db.execute(stmt)
        return list(result.scalars().all())
    finally:
        await db.close()


async def get_element_by_id(
    model: Type[ModelType],
    db_session: Callable[[], AsyncSession],
    id: Union[int, str]
) -> ModelType:
    """Get single element by ID from database (async).
    
    Args:
        model: SQLAlchemy model class
        db_session: Async database session factory function
        id: Element ID to retrieve
        
    Returns:
        Model instance
        
    Raises:
        HTTPException: If element not found
    """
    db = db_session()
    try:
        from sqlalchemy import select
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


async def create_element(
    model: Type[ModelType],
    db_session: Callable[[], AsyncSession],
    data: Dict[str, Any]
) -> ModelType:
    """Create new element in database (async).
    
    Args:
        model: SQLAlchemy model class
        db_session: Async database session factory function
        data: Dictionary with data for new element
        
    Returns:
        Created model instance
        
    Raises:
        HTTPException: If creation fails
    """
    db = db_session()
    try:
        # Validate required fields for creation
        # Check model columns for non-nullable fields (excluding id and auto-generated fields)
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


async def update_element(
    model: Type[ModelType],
    db_session: Callable[[], AsyncSession],
    id: Union[int, str],
    data: Dict[str, Any],
    partial: bool = False
) -> ModelType:
    """Update element in database (async).
    
    Args:
        model: SQLAlchemy model class
        db_session: Async database session factory function
        id: Element ID to update
        data: Dictionary with data to update
        partial: If True, update only provided fields (PATCH). If False, replace all fields (PUT).
        
    Returns:
        Updated model instance
        
    Raises:
        HTTPException: If update fails or element not found
    """
    db = db_session()
    try:
        result = await db.get(model, id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Element with id {id} not found"
            )
        
        if partial:
            # PATCH: update only provided fields, skip None values
            data = {key: value for key, value in dict(data).items() if value is not None}
        else:
            # PUT: replace all fields with provided values, use None for missing fields
            # Get all column names from the model, excluding primary keys
            all_columns = {col.name for col in model.__table__.columns if not col.primary_key}
            # For PUT, we need all fields - use provided values or None
            data = {col: data.get(col, None) for col in all_columns}
        
        # Skip update if data is empty (for PATCH with empty dict)
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


async def delete_element(
    model: Type[ModelType],
    db_session: Callable[[], AsyncSession],
    id: Union[int, str]
) -> bool:
    """Delete element from database by ID (async).
    
    Args:
        model: SQLAlchemy model class
        db_session: Async database session factory function
        id: Element ID to delete
        
    Returns:
        True if deletion was successful
        
    Raises:
        HTTPException: If deletion fails or element not found
    """
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

