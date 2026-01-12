# FastAPI ViewSets

[![Python Version](https://img.shields.io/badge/python-3.6%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![PyPI version](https://badge.fury.io/py/fastapi-viewsets.svg)](https://badge.fury.io/py/fastapi-viewsets)

A powerful package for creating REST API endpoints with FastAPI and SQLAlchemy. Automatically generates CRUD operations (Create, Read, Update, Delete) for your database models, similar to Django REST Framework's ViewSets.

## Features

- 🚀 **Automatic CRUD endpoints** - Generate REST API endpoints automatically
- 🔒 **OAuth2 support** - Built-in authentication protection for endpoints
- ⚡ **Async support** - Full async/await support for high-performance applications
- 📝 **Type hints** - Full type annotation support for better IDE experience
- 🎯 **Flexible** - Choose which HTTP methods to enable
- 🔧 **Easy to use** - Simple API, minimal boilerplate code

## Installation

Install the package using pip:

```bash
pip install fastapi-viewsets
```

For async support, you'll also need an async database driver:

```bash
# For SQLite
pip install aiosqlite

# For PostgreSQL
pip install asyncpg

# For MySQL
pip install aiomysql
```

## Quick Start

### Synchronous Example

Create a `main.py` file:

```python
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Boolean
from fastapi_viewsets import BaseViewset
from fastapi_viewsets.db_conf import Base, get_session, engine

# Create FastAPI app
app = FastAPI()

# Define Pydantic schema
class UserSchema(BaseModel):
    """Pydantic Schema"""
    id: Optional[int] = None
    username: str
    password: str
    is_admin: Optional[bool] = False

    class Config:
        orm_mode = True

# Define SQLAlchemy model
class User(Base):
    """SQLAlchemy model"""
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String(255))
    is_admin = Column(Boolean, default=False)

# Create database tables
Base.metadata.create_all(engine)

# Create viewset
user_viewset = BaseViewset(
    endpoint='/user',
    model=User,
    response_model=UserSchema,
    db_session=get_session,
    tags=['Users']
)

# Register all CRUD methods
user_viewset.register()

# Include router in FastAPI app
app.include_router(user_viewset)
```

Run the application:

```bash
uvicorn main:app --reload
```

Visit the interactive API documentation at [http://localhost:8000/docs](http://localhost:8000/docs)

### Async Example

For async support, use `AsyncBaseViewset`:

```python
from typing import Optional
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Boolean
from fastapi_viewsets import AsyncBaseViewset
from fastapi_viewsets.db_conf import Base, get_async_session, engine

# Create FastAPI app
app = FastAPI()

# Define Pydantic schema
class UserSchema(BaseModel):
    """Pydantic Schema"""
    id: Optional[int] = None
    username: str
    password: str
    is_admin: Optional[bool] = False

    class Config:
        orm_mode = True

# Define SQLAlchemy model
class User(Base):
    """SQLAlchemy model"""
    __tablename__ = "user"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True)
    password = Column(String(255))
    is_admin = Column(Boolean, default=False)

# Create database tables
Base.metadata.create_all(engine)

# Create async viewset
user_viewset = AsyncBaseViewset(
    endpoint='/user',
    model=User,
    response_model=UserSchema,
    db_session=get_async_session,
    tags=['Users']
)

# Register all CRUD methods
user_viewset.register()

# Include router in FastAPI app
app.include_router(user_viewset)
```

## Authentication Example

You can protect endpoints with OAuth2:

```python
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi_viewsets import BaseViewset
from fastapi_viewsets.db_conf import Base, get_session, engine
from starlette import status

app = FastAPI()

# ... define User model and schema ...

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create protected viewset
protected_viewset = BaseViewset(
    endpoint='/user',
    model=User,
    response_model=UserSchema,
    db_session=get_session,
    tags=['Protected Users']
)

# Register methods with authentication
protected_viewset.register(
    methods=['LIST', 'POST', 'GET', 'PUT'],
    protected_methods=['LIST', 'POST', 'GET', 'PUT'],
    oauth_protect=oauth2_scheme
)

app.include_router(protected_viewset)

# Token endpoint
@app.post('/token')
def generate_token(form_data: OAuth2PasswordRequestForm = Depends()):
    # Your token generation logic here
    pass
```

## Available HTTP Methods

The following HTTP methods are supported:

- `LIST` - GET request to list all items (with pagination)
- `GET` - GET request to retrieve a single item by ID
- `POST` - POST request to create a new item
- `PUT` - PUT request to replace an entire item
- `PATCH` - PATCH request to partially update an item
- `DELETE` - DELETE request to delete an item

### Selecting Specific Methods

You can register only specific methods:

```python
user_viewset.register(methods=['LIST', 'GET', 'POST'])
```

## Database Configuration

### ORM Selection

`fastapi_viewsets` supports multiple ORM libraries. You can choose which ORM to use by setting the `ORM_TYPE` environment variable.

### Environment Variables

Create a `.env` file in your project root:

#### SQLAlchemy (Default)

```env
ORM_TYPE=sqlalchemy
SQLALCHEMY_DATABASE_URL=sqlite:///path/to/db/base.db
```

Or for PostgreSQL:

```env
ORM_TYPE=sqlalchemy
SQLALCHEMY_DATABASE_URL=postgresql://username:password@localhost:5432/mydatabase
```

For async databases, you can also specify:

```env
ORM_TYPE=sqlalchemy
SQLALCHEMY_DATABASE_URL=postgresql://username:password@localhost:5432/mydatabase
SQLALCHEMY_ASYNC_DATABASE_URL=postgresql+asyncpg://username:password@localhost:5432/mydatabase
```

#### Tortoise ORM

```env
ORM_TYPE=tortoise
TORTOISE_DATABASE_URL=postgresql://username:password@localhost:5432/mydatabase
TORTOISE_MODELS=["app.models"]
TORTOISE_APP_LABEL=models
```

Or use JSON format for models:

```env
ORM_TYPE=tortoise
TORTOISE_DATABASE_URL=postgresql://username:password@localhost:5432/mydatabase
TORTOISE_MODELS=["app.models", "app.other_models"]
```

#### Peewee

```env
ORM_TYPE=peewee
PEEWEE_DATABASE_URL=postgresql://username:password@localhost:5432/mydatabase
```

Or for SQLite:

```env
ORM_TYPE=peewee
PEEWEE_DATABASE_URL=sqlite:///path/to/db/base.db
```

### Supported ORMs and Databases

- **SQLAlchemy** (default)
  - SQLite (synchronous and async with `aiosqlite`)
  - PostgreSQL (synchronous and async with `asyncpg`)
  - MySQL (synchronous and async with `aiomysql`)
  
- **Tortoise ORM** (async-only)
  - PostgreSQL (with `asyncpg`)
  - MySQL (with `aiomysql`)
  - SQLite (with `aiosqlite`)
  
- **Peewee** (sync-only)
  - SQLite
  - PostgreSQL
  - MySQL

### Installation of ORM-specific Dependencies

Install the ORM you want to use:

```bash
# For SQLAlchemy (default, already included)
pip install SQLAlchemy

# For Tortoise ORM
pip install tortoise-orm asyncpg  # or aiomysql for MySQL

# For Peewee
pip install peewee
```

For async support with SQLAlchemy, install the appropriate driver:

```bash
# For SQLite
pip install aiosqlite

# For PostgreSQL
pip install asyncpg

# For MySQL
pip install aiomysql
```

## API Reference

### BaseViewset

Synchronous viewset class for CRUD operations.

**Parameters:**
- `endpoint` (str): Base endpoint path (e.g., '/user')
- `model`: ORM model class (SQLAlchemy, Tortoise, Peewee, etc.)
- `response_model`: Pydantic model for response serialization
- `db_session` (Callable): Database session factory function
- `orm_adapter` (BaseORMAdapter, optional): ORM adapter instance. If not provided, uses default from configuration.
- `tags` (List[str]): Tags for OpenAPI documentation
- `allowed_methods` (List[str], optional): List of allowed methods

**Methods:**
- `register(methods=None, oauth_protect=None, protected_methods=None)`: Register CRUD endpoints

### AsyncBaseViewset

Asynchronous viewset class for CRUD operations.

Same parameters and methods as `BaseViewset`, but all operations are async.

### ORM Adapters

The library supports multiple ORM adapters through the `BaseORMAdapter` interface:

- **SQLAlchemyAdapter**: For SQLAlchemy ORM (default)
- **TortoiseAdapter**: For Tortoise ORM (async-only)
- **PeeweeAdapter**: For Peewee ORM (sync-only)

You can get the default adapter from configuration:

```python
from fastapi_viewsets.db_conf import get_orm_adapter

adapter = get_orm_adapter()  # Reads ORM_TYPE from environment
```

Or create a specific adapter:

```python
from fastapi_viewsets.orm.factory import ORMFactory

# Create SQLAlchemy adapter
adapter = ORMFactory.create_adapter('sqlalchemy', {
    'database_url': 'postgresql://user:pass@localhost/db'
})

# Create Tortoise adapter
adapter = ORMFactory.create_adapter('tortoise', {
    'database_url': 'postgresql://user:pass@localhost/db',
    'models': ['app.models']
})
```

## Differences Between PUT and PATCH

- **PUT**: Replaces the entire object. All fields must be provided (missing fields will be set to None).
- **PATCH**: Partially updates the object. Only provided fields will be updated.

## Error Handling

The library provides comprehensive error handling:

- `404 Not Found`: When an element is not found
- `400 Bad Request`: For validation errors and database integrity errors
- Detailed error messages for debugging

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author

Alexander Valenchits

## Links

- [GitHub Repository](https://github.com/svalench/fastapi_viewsets)
- [PyPI Package](https://pypi.org/project/fastapi-viewsets/)
