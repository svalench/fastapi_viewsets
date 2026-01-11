# Release v0.1.5

## 🎉 What's New

This release brings significant improvements to the FastAPI ViewSets library, making it more robust, feature-rich, and production-ready.

## ✨ New Features

- **Full Async Support**: Complete async/await support with `AsyncBaseViewset` for high-performance applications
- **Comprehensive Type Hints**: Full type annotation support throughout the codebase
- **PUT vs PATCH Support**: Proper distinction between PUT (full replacement) and PATCH (partial update) operations
- **Improved Error Handling**: Enhanced error handling with specific exceptions for integrity and database errors

## 🐛 Bug Fixes

- Fixed 405 Method Not Allowed error for LIST endpoints
- Fixed database session leaks by ensuring proper session cleanup
- Fixed PUT/PATCH update logic to correctly handle partial updates
- Fixed limit=0 handling to return empty list instead of all items
- Fixed primary key exclusion in PUT updates

## 🔧 Improvements

- Better database session management with proper cleanup
- Enhanced route registration to prevent conflicts
- Improved code quality and structure
- Updated documentation with comprehensive examples

## 📦 Installation

```bash
pip install fastapi-viewsets
```

For async support:
```bash
pip install fastapi-viewsets aiosqlite
```

## 📚 Documentation

- [Full Documentation](https://github.com/svalench/fastapi_viewsets#readme)
- [Examples](https://github.com/svalench/fastapi_viewsets#quick-start)

## 🧪 Testing

- 108+ comprehensive tests
- 86% code coverage
- Full sync and async test coverage

---

**Full Changelog**: https://github.com/svalench/fastapi_viewsets/compare/v0.1.4...v0.1.5

