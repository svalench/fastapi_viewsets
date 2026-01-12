"""ORM adapters for different database libraries."""

from fastapi_viewsets.orm.base import BaseORMAdapter
from fastapi_viewsets.orm.factory import ORMFactory

__all__ = ['BaseORMAdapter', 'ORMFactory']

# Try to import adapters (they may not be available if dependencies are not installed)
try:
    from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
    __all__.append('SQLAlchemyAdapter')
except ImportError:
    pass

try:
    from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
    __all__.append('TortoiseAdapter')
except ImportError:
    pass

try:
    from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
    __all__.append('PeeweeAdapter')
except ImportError:
    pass

