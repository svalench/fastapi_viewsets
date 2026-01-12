"""Base abstract class for ORM adapters."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Union, Type, TypeVar, List, Callable

# Type variable for ORM models
ModelType = TypeVar('ModelType')


class BaseORMAdapter(ABC):
    """Abstract base class for ORM adapters.
    
    This class defines the interface that all ORM adapters must implement
    to work with fastapi_viewsets. Each ORM (SQLAlchemy, Tortoise, Peewee)
    should have its own adapter implementation.
    """
    
    @abstractmethod
    def get_session(self) -> Any:
        """Get synchronous database session.
        
        Returns:
            Database session object (type depends on ORM)
        """
        pass
    
    @abstractmethod
    def get_async_session(self) -> Any:
        """Get asynchronous database session.
        
        Returns:
            Async database session object (type depends on ORM)
            
        Raises:
            NotImplementedError: If async operations are not supported
        """
        pass
    
    @abstractmethod
    def get_base(self) -> Type:
        """Get base class for ORM models.
        
        Returns:
            Base class that models should inherit from
        """
        pass
    
    @abstractmethod
    def get_list_queryset(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """Get list of elements from database with pagination support (synchronous).
        
        Args:
            model: ORM model class
            db_session: Database session factory function
            limit: Maximum number of items to return
            offset: Number of items to skip
            
        Returns:
            List of model instances
        """
        pass
    
    @abstractmethod
    async def get_list_queryset_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        limit: Optional[int] = None,
        offset: Optional[int] = None
    ) -> List[ModelType]:
        """Get list of elements from database with pagination support (asynchronous).
        
        Args:
            model: ORM model class
            db_session: Async database session factory function
            limit: Maximum number of items to return
            offset: Number of items to skip
            
        Returns:
            List of model instances
        """
        pass
    
    @abstractmethod
    def get_element_by_id(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> ModelType:
        """Get single element by ID from database (synchronous).
        
        Args:
            model: ORM model class
            db_session: Database session factory function
            id: Element ID to retrieve
            
        Returns:
            Model instance
            
        Raises:
            HTTPException: If element not found
        """
        pass
    
    @abstractmethod
    async def get_element_by_id_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> ModelType:
        """Get single element by ID from database (asynchronous).
        
        Args:
            model: ORM model class
            db_session: Async database session factory function
            id: Element ID to retrieve
            
        Returns:
            Model instance
            
        Raises:
            HTTPException: If element not found
        """
        pass
    
    @abstractmethod
    def create_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        data: Dict[str, Any]
    ) -> ModelType:
        """Create new element in database (synchronous).
        
        Args:
            model: ORM model class
            db_session: Database session factory function
            data: Dictionary with data for new element
            
        Returns:
            Created model instance
            
        Raises:
            HTTPException: If creation fails
        """
        pass
    
    @abstractmethod
    async def create_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        data: Dict[str, Any]
    ) -> ModelType:
        """Create new element in database (asynchronous).
        
        Args:
            model: ORM model class
            db_session: Async database session factory function
            data: Dictionary with data for new element
            
        Returns:
            Created model instance
            
        Raises:
            HTTPException: If creation fails
        """
        pass
    
    @abstractmethod
    def update_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False
    ) -> ModelType:
        """Update element in database (synchronous).
        
        Args:
            model: ORM model class
            db_session: Database session factory function
            id: Element ID to update
            data: Dictionary with data to update
            partial: If True, update only provided fields (PATCH). 
                    If False, replace all fields (PUT).
            
        Returns:
            Updated model instance
            
        Raises:
            HTTPException: If update fails or element not found
        """
        pass
    
    @abstractmethod
    async def update_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str],
        data: Dict[str, Any],
        partial: bool = False
    ) -> ModelType:
        """Update element in database (asynchronous).
        
        Args:
            model: ORM model class
            db_session: Async database session factory function
            id: Element ID to update
            data: Dictionary with data to update
            partial: If True, update only provided fields (PATCH). 
                    If False, replace all fields (PUT).
            
        Returns:
            Updated model instance
            
        Raises:
            HTTPException: If update fails or element not found
        """
        pass
    
    @abstractmethod
    def delete_element(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> bool:
        """Delete element from database by ID (synchronous).
        
        Args:
            model: ORM model class
            db_session: Database session factory function
            id: Element ID to delete
            
        Returns:
            True if deletion was successful
            
        Raises:
            HTTPException: If deletion fails or element not found
        """
        pass
    
    @abstractmethod
    async def delete_element_async(
        self,
        model: Type[ModelType],
        db_session: Callable[[], Any],
        id: Union[int, str]
    ) -> bool:
        """Delete element from database by ID (asynchronous).
        
        Args:
            model: ORM model class
            db_session: Async database session factory function
            id: Element ID to delete
            
        Returns:
            True if deletion was successful
            
        Raises:
            HTTPException: If deletion fails or element not found
        """
        pass
    
    @abstractmethod
    def get_model_columns(self, model: Type[ModelType]) -> Dict[str, Any]:
        """Get model column information.
        
        Args:
            model: ORM model class
            
        Returns:
            Dictionary with column information (name, nullable, primary_key, etc.)
        """
        pass

