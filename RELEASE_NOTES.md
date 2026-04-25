# Release Notes

## Version 1.2.1

### 🐛 Bugfix

- **`SQLAlchemyAdapter` no longer crashes at construction** when the
  async DB-API driver (`aiosqlite` / `asyncpg` / `aiomysql`) is missing.
  Sync-only setups keep working out of the box; `get_async_session()`
  raises a helpful `RuntimeError` lazily if you try to use async without
  the driver. Regression introduced in 1.2.0 by always passing an
  explicit `async_database_url` from `ORMFactory.get_adapter_from_env`.

### 📦 Packaging

- Switched to `[tool.setuptools.packages.find]` so future subpackages are
  picked up automatically by wheel/sdist builds.

## Version 1.2.0

### ✨ Highlights

- **Pydantic v2 first**. CRUD handlers serialize bodies with
  `model_dump(exclude_unset=...)`, fixing PATCH semantics so unset
  fields are no longer overwritten with defaults.
- **Lazy `db_conf`**. Importing `fastapi_viewsets` no longer creates
  SQLAlchemy engines unless they are accessed, and no longer fails
  when an async driver such as `aiosqlite` is missing.
- **Single source of truth** for sync→async URL conversion
  (`to_async_database_url`) and for the default ORM adapter singleton
  (`ORMFactory.get_default_adapter`).
- **Internal refactor**. `BaseViewset.register` and
  `AsyncBaseViewset.register` were deduplicated into a shared
  `_RegisterMixin`. Bare `except: pass` blocks were replaced with
  narrow guards. The no-op auth dependency `butle` was renamed to
  `_noop_dependency` (the old name remains as an alias).

### 📦 Packaging

- Added PEP 621 `pyproject.toml` and trimmed `setup.py` to a shim.
- `python_requires>=3.9`, `pydantic>=2.5,<3`, `fastapi>=0.110`.
- Pre-configured `[tool.ruff]`, `[tool.black]`, `[tool.mypy]`, plus a
  `lint` extra that pulls in ruff/black/mypy.

### 🔄 Backward compatibility

- The `butle` no-op dependency name still works.
- Pydantic v1 schemas keep working via a transparent fallback in
  `fastapi_viewsets._compat.model_to_dict`, but the test matrix now
  targets Pydantic v2.
- `BaseViewset` / `AsyncBaseViewset` public APIs are unchanged.

Details: [RELEASE_1.2.0.md](RELEASE_1.2.0.md).

## Version 1.1.0

### 🎉 What's New

This major release introduces **multi-ORM support**, allowing you to choose between SQLAlchemy, Tortoise ORM, and Peewee. The library now uses an adapter pattern to provide a unified interface for different ORM implementations, making it more flexible and extensible.

### ✨ New Features

- **Multi-ORM Support**: Choose your preferred ORM - SQLAlchemy (default), Tortoise ORM, or Peewee
- **ORM Adapter Pattern**: Unified interface for all ORM operations through `BaseORMAdapter`
- **ORMFactory**: Factory class for creating and managing ORM adapters based on configuration
- **Environment-based Configuration**: Configure your ORM choice through environment variables (`ORM_TYPE`)
- **Flexible Database Configuration**: Support for different database URLs per ORM type
- **Backward Compatibility**: Existing SQLAlchemy code continues to work without changes

### 🔧 Improvements

- **Modular Architecture**: Clean separation of ORM-specific logic into adapters
- **Better Code Organization**: ORM adapters are now in a dedicated `orm` package
- **Enhanced Configuration**: Support for ORM-specific configuration through environment variables
- **Improved Error Handling**: Better error messages for missing ORM dependencies
- **Code Quality**: Improved code structure and maintainability

### 📦 Dependencies

- FastAPI >= 0.76.0
- SQLAlchemy >= 1.4.36 (default, core dependency)
- Python >= 3.6

**Optional Dependencies:**
- `tortoise-orm>=0.20.0` and `asyncpg>=0.28.0` for Tortoise ORM support
- `peewee>=3.17.0` for Peewee ORM support

### 🧪 Testing

- Comprehensive test suite with 200+ tests
- 70%+ code coverage
- Unit tests for all ORM adapters
- Integration tests for each ORM
- Edge case and error handling tests
- Both sync and async test coverage

### 📚 Documentation

- Updated README with multi-ORM configuration examples
- Added ORM adapter documentation
- Configuration examples for each supported ORM
- Migration guide for existing users

### 🚀 Migration Guide

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

### 🔌 ORM Adapters

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

### 📝 Configuration

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

### 🙏 Acknowledgments

Thank you to all contributors and users who provided feedback and reported issues!

---

## Version 1.0.1

### 🎉 What's New

This release brings significant improvements to the FastAPI ViewSets library, making it more robust, feature-rich, and production-ready.

### ✨ New Features

- **Full Async Support**: Complete async/await support with `AsyncBaseViewset` for high-performance applications
- **Comprehensive Type Hints**: Full type annotation support throughout the codebase for better IDE experience and code maintainability
- **Improved Error Handling**: Enhanced error handling with specific exceptions for integrity errors and database errors
- **PUT vs PATCH Support**: Proper distinction between PUT (full replacement) and PATCH (partial update) operations
- **Route Registration Improvements**: Fixed route registration order to properly handle LIST and GET endpoints

### 🐛 Bug Fixes

- Fixed 405 Method Not Allowed error for LIST endpoints
- Fixed database session leaks by ensuring proper session cleanup
- Fixed PUT/PATCH update logic to correctly handle partial updates
- Fixed limit=0 handling to return empty list instead of all items
- Fixed primary key exclusion in PUT updates
- Improved validation for required fields during creation

### 🔧 Improvements

- **Better Database Session Management**: Proper try/finally blocks to ensure sessions are always closed
- **Enhanced Route Registration**: Improved order of route registration to prevent conflicts between LIST and GET endpoints
- **Code Quality**: Removed unused code, improved code structure and organization
- **Documentation**: Updated README with comprehensive examples and API descriptions

### 📦 Dependencies

- FastAPI >= 0.76.0
- SQLAlchemy >= 1.4.36
- Python >= 3.6

### 🧪 Testing

- Comprehensive test suite with 108+ tests
- 86% code coverage
- Unit tests for all core components
- Integration tests for full CRUD workflows
- Edge case testing
- Both sync and async test coverage

### 📚 Documentation

- Updated README with async examples
- Improved code examples
- Better API documentation
- Clear distinction between sync and async usage

### 🚀 Migration Guide

If you're upgrading from a previous version:

1. **Async Support**: If you want to use async features, install an async database driver:
   ```bash
   pip install aiosqlite  # for SQLite
   # or
   pip install asyncpg   # for PostgreSQL
   ```

2. **PUT/PATCH**: PUT now performs full replacement (sets missing fields to None), while PATCH only updates provided fields. Make sure your Pydantic schemas support optional fields for PATCH operations.

3. **Route Registration**: The library now automatically handles route registration order. No changes needed in your code.

### 🙏 Acknowledgments

Thank you to all contributors and users who provided feedback and reported issues!

---

## Installation

```bash
pip install fastapi-viewsets
```

For async support:
```bash
pip install fastapi-viewsets aiosqlite
```

## Quick Start

```python
from fastapi import FastAPI
from fastapi_viewsets import BaseViewset
from fastapi_viewsets.db_conf import Base, get_session, engine

app = FastAPI()

# Define your model and schema
# ... (see README for full example)

# Create viewset
user_viewset = BaseViewset(
    endpoint='/users',
    model=User,
    response_model=UserSchema,
    db_session=get_session,
    tags=['Users']
)

# Register endpoints
user_viewset.register()

# Include in app
app.include_router(user_viewset)
```

## Links

- [GitHub Repository](https://github.com/svalench/fastapi_viewsets)
- [PyPI Package](https://pypi.org/project/fastapi-viewsets/)
- [Documentation](https://github.com/svalench/fastapi_viewsets#readme)

