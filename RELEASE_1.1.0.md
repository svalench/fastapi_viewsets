# Release v1.1.0

## 🎉 What's New

This major release introduces **multi-ORM support**, allowing you to choose between SQLAlchemy, Tortoise ORM, and Peewee. The library now uses an adapter pattern to provide a unified interface for different ORM implementations, making it more flexible and extensible.

## ✨ New Features

- **Multi-ORM Support**: Choose your preferred ORM - SQLAlchemy (default), Tortoise ORM, or Peewee
- **ORM Adapter Pattern**: Unified interface for all ORM operations through `BaseORMAdapter`
- **ORMFactory**: Factory class for creating and managing ORM adapters based on configuration
- **Environment-based Configuration**: Configure your ORM choice through environment variables (`ORM_TYPE`)
- **Flexible Database Configuration**: Support for different database URLs per ORM type
- **Backward Compatibility**: Existing SQLAlchemy code continues to work without changes

## 🔧 Improvements

- **Modular Architecture**: Clean separation of ORM-specific logic into adapters
- **Better Code Organization**: ORM adapters are now in a dedicated `orm` package
- **Enhanced Configuration**: Support for ORM-specific configuration through environment variables
- **Improved Error Handling**: Better error messages for missing ORM dependencies
- **Code Quality**: Improved code structure and maintainability

## 📦 Dependencies

- FastAPI >= 0.76.0
- SQLAlchemy >= 1.4.36 (default, core dependency)
- Python >= 3.6

**Optional Dependencies:**
- `tortoise-orm>=0.20.0` and `asyncpg>=0.28.0` for Tortoise ORM support
- `peewee>=3.17.0` for Peewee ORM support

## 🧪 Testing

- Comprehensive test suite with 200+ tests
- 70%+ code coverage
- Unit tests for all ORM adapters
- Integration tests for each ORM
- Edge case and error handling tests
- Both sync and async test coverage

## 📚 Documentation

- Updated README with multi-ORM configuration examples
- Added ORM adapter documentation
- Configuration examples for each supported ORM
- Migration guide for existing users

## 🚀 Migration Guide

If you're upgrading from version 1.0.1:

1. **No Breaking Changes**: Existing code using SQLAlchemy will continue to work without modifications. SQLAlchemy remains the default ORM.

2. **Using a Different ORM**: To use Tortoise or Peewee, set the `ORM_TYPE` environment variable:
   ```bash
   # For Tortoise ORM
   export ORM_TYPE=tortoise
   export DATABASE_URL=postgresql://user:pass@localhost/db
   export TORTOISE_MODELS=["app.models"]
   
   # For Peewee ORM
   export ORM_TYPE=peewee
   export DATABASE_URL=sqlite:///database.db
   ```

3. **Custom Adapter**: You can now pass a custom `orm_adapter` to viewsets:
   ```python
   from fastapi_viewsets.orm.factory import ORMFactory
   
   adapter = ORMFactory.create_adapter('sqlalchemy', {
       'database_url': 'postgresql://...'
   })
   
   viewset = BaseViewset(
       model=User,
       orm_adapter=adapter,
       ...
   )
   ```

## 🔌 ORM Adapters

The library now supports three ORM adapters:

1. **SQLAlchemyAdapter** (default)
   - Full sync and async support
   - Works with all SQLAlchemy-compatible databases

2. **TortoiseAdapter**
   - Async-only ORM
   - Perfect for high-performance async applications
   - Requires `tortoise-orm` and async database drivers

3. **PeeweeAdapter**
   - Sync-only ORM
   - Lightweight and simple
   - Requires `peewee`

## 📝 Configuration

Configure your ORM through environment variables in `.env`:

```env
# Choose your ORM
ORM_TYPE=sqlalchemy  # or 'tortoise' or 'peewee'

# Database URL (used by all ORMs)
DATABASE_URL=postgresql://user:pass@localhost/db

# SQLAlchemy-specific
SQLALCHEMY_DATABASE_URL=postgresql://user:pass@localhost/db
SQLALCHEMY_ASYNC_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/db

# Tortoise-specific
TORTOISE_DATABASE_URL=postgresql://user:pass@localhost/db
TORTOISE_MODELS=["app.models", "app.other"]
TORTOISE_APP_LABEL=models

# Peewee-specific
PEEWEE_DATABASE_URL=sqlite:///database.db
```

## 📦 Installation

```bash
pip install fastapi-viewsets
```

For specific ORM support:

```bash
# For Tortoise ORM
pip install fastapi-viewsets[tortoise]

# For Peewee ORM
pip install fastapi-viewsets[peewee]
```

## 🔗 Links

- [GitHub Repository](https://github.com/svalench/fastapi_viewsets)
- [PyPI Package](https://pypi.org/project/fastapi-viewsets/)
- [Full Documentation](https://github.com/svalench/fastapi_viewsets#readme)

---

**Full Changelog**: https://github.com/svalench/fastapi_viewsets/compare/v1.0.1...v1.1.0

