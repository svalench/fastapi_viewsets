# Release Notes

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

