"""Factory for creating ORM adapters based on configuration."""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from fastapi_viewsets.constants import BASE_DIR
from fastapi_viewsets.orm.base import BaseORMAdapter

# Load environment variables
load_dotenv(f"{BASE_DIR}.env")

# Global adapter instance
_default_adapter: Optional[BaseORMAdapter] = None


class ORMFactory:
    """Factory for creating ORM adapters."""
    
    _adapters: Dict[str, type] = {}
    
    @classmethod
    def register_adapter(cls, orm_type: str, adapter_class: type):
        """Register an ORM adapter class.
        
        Args:
            orm_type: Name of the ORM (e.g., 'sqlalchemy', 'tortoise', 'peewee')
            adapter_class: Adapter class that inherits from BaseORMAdapter
        """
        cls._adapters[orm_type.lower()] = adapter_class
    
    @classmethod
    def create_adapter(
        cls,
        orm_type: str,
        config: Optional[Dict[str, Any]] = None
    ) -> BaseORMAdapter:
        """Create an ORM adapter instance.
        
        Args:
            orm_type: Type of ORM ('sqlalchemy', 'tortoise', 'peewee')
            config: Configuration dictionary for the adapter
            
        Returns:
            ORM adapter instance
            
        Raises:
            ValueError: If orm_type is not registered
        """
        orm_type = orm_type.lower()
        
        if orm_type not in cls._adapters:
            raise ValueError(
                f"Unknown ORM type: {orm_type}. "
                f"Available types: {', '.join(cls._adapters.keys())}"
            )
        
        adapter_class = cls._adapters[orm_type]
        config = config or {}
        
        return adapter_class(**config)
    
    @classmethod
    def get_adapter_from_env(cls) -> BaseORMAdapter:
        """Get ORM adapter from environment variables.
        
        Reads ORM_TYPE and related configuration from environment variables.
        
        Returns:
            ORM adapter instance
            
        Raises:
            ValueError: If ORM_TYPE is not set or invalid
        """
        orm_type = os.getenv('ORM_TYPE', 'sqlalchemy').lower()
        config = {}
        
        if orm_type == 'sqlalchemy':
            database_url = os.getenv('SQLALCHEMY_DATABASE_URL') or os.getenv('DATABASE_URL')
            if not database_url:
                database_url = f"sqlite:///{BASE_DIR}base.db"
            
            async_database_url = os.getenv('SQLALCHEMY_ASYNC_DATABASE_URL')
            if not async_database_url:
                # Auto-convert sync URL to async
                if database_url.startswith('sqlite:///'):
                    async_database_url = database_url.replace('sqlite:///', 'sqlite+aiosqlite:///', 1)
                elif database_url.startswith('postgresql://'):
                    async_database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
                elif database_url.startswith('mysql://'):
                    async_database_url = database_url.replace('mysql://', 'mysql+aiomysql://', 1)
            
            config = {
                'database_url': database_url,
                'async_database_url': async_database_url
            }
        
        elif orm_type == 'tortoise':
            database_url = os.getenv('TORTOISE_DATABASE_URL') or os.getenv('DATABASE_URL')
            if not database_url:
                raise ValueError("TORTOISE_DATABASE_URL or DATABASE_URL must be set")
            
            models_str = os.getenv('TORTOISE_MODELS', '[]')
            import json
            try:
                models = json.loads(models_str)
            except json.JSONDecodeError:
                # Try comma-separated list
                models = [m.strip() for m in models_str.split(',') if m.strip()]
            
            app_label = os.getenv('TORTOISE_APP_LABEL', 'models')
            
            config = {
                'database_url': database_url,
                'models': models,
                'app_label': app_label
            }
        
        elif orm_type == 'peewee':
            database_url = os.getenv('PEEWEE_DATABASE_URL') or os.getenv('DATABASE_URL')
            if not database_url:
                database_url = f"sqlite:///{BASE_DIR}base.db"
            
            config = {
                'database_url': database_url
            }
        
        else:
            raise ValueError(
                f"Unknown ORM_TYPE: {orm_type}. "
                f"Supported types: sqlalchemy, tortoise, peewee"
            )
        
        return cls.create_adapter(orm_type, config)
    
    @classmethod
    def get_default_adapter(cls) -> BaseORMAdapter:
        """Get or create default adapter instance.
        
        Returns:
            Default ORM adapter instance (singleton)
        """
        global _default_adapter
        if _default_adapter is None:
            _default_adapter = cls.get_adapter_from_env()
        return _default_adapter


# Register built-in adapters
def _register_builtin_adapters():
    """Register built-in ORM adapters."""
    try:
        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
        ORMFactory.register_adapter('sqlalchemy', SQLAlchemyAdapter)
    except ImportError:
        pass
    
    try:
        from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
        ORMFactory.register_adapter('tortoise', TortoiseAdapter)
    except ImportError:
        pass
    
    try:
        from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
        ORMFactory.register_adapter('peewee', PeeweeAdapter)
    except ImportError:
        pass


# Auto-register on import
_register_builtin_adapters()

