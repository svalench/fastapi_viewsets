# FastAPI ViewSets

[![PyPI version](https://badge.fury.io/py/fastapi-viewsets.svg)](https://badge.fury.io/py/fastapi-viewsets)
[![Python Version](https://img.shields.io/pypi/pyversions/fastapi-viewsets.svg)](https://pypi.org/project/fastapi-viewsets/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Downloads](https://img.shields.io/pypi/dm/fastapi-viewsets.svg)](https://pypi.org/project/fastapi-viewsets/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red)](https://sqlalchemy.org)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2-blueviolet)](https://docs.pydantic.dev)

> **Django REST Framework-style ViewSets for FastAPI** — auto-generate CRUD endpoints from SQLAlchemy, Tortoise ORM, or Peewee models in minutes.

```bash
pip install fastapi-viewsets
```

## Why fastapi-viewsets?

FastAPI is powerful but writing CRUD routers is repetitive. This library brings the DRF ViewSet pattern to FastAPI:

- **One class → six endpoints** (LIST, GET, POST, PUT, PATCH, DELETE) — no boilerplate
- **Multi-ORM** — SQLAlchemy (sync + async), Tortoise ORM, Peewee
- **OAuth2 per-method protection** — protect only the methods you want
- **Async-first** — full `async/await` support via `AsyncBaseViewset`
- **Auto-pagination** on LIST endpoints
- **OpenAPI docs** generated automatically with proper tags

## Installation

```bash
# Base install
pip install fastapi-viewsets

# With async DB drivers
pip install fastapi-viewsets aiosqlite          # SQLite async
pip install fastapi-viewsets asyncpg            # PostgreSQL async
pip install fastapi-viewsets aiomysql           # MySQL async

# Alternative ORMs
pip install fastapi-viewsets tortoise-orm       # Tortoise ORM
pip install fastapi-viewsets peewee             # Peewee ORM
```

## Quick Start

### Synchronous (SQLAlchemy)

```python
from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String
from fastapi_viewsets import BaseViewset
from fastapi_viewsets.db_conf import Base, get_session, engine

app = FastAPI()

class UserSchema(BaseModel):
    id: int | None = None
    username: str
    class Config:
        orm_mode = True

class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)

Base.metadata.create_all(engine)

user_viewset = BaseViewset(
    endpoint='/users',
    model=User,
    response_model=UserSchema,
    db_session=get_session,
    tags=['Users']
)
user_viewset.register()   # registers LIST, GET, POST, PUT, PATCH, DELETE
app.include_router(user_viewset)
```

Run: `uvicorn main:app --reload` → visit `http://localhost:8000/docs` ✅

### Async (SQLAlchemy async)

```python
from fastapi_viewsets import AsyncBaseViewset
from fastapi_viewsets.db_conf import get_async_session

user_viewset = AsyncBaseViewset(
    endpoint='/users',
    model=User,
    response_model=UserSchema,
    db_session=get_async_session,
    tags=['Users']
)
user_viewset.register()
app.include_router(user_viewset)
```

### Select specific methods

```python
# Read-only public, write operations protected by OAuth2
from fastapi.security import OAuth2PasswordBearer

oauth2 = OAuth2PasswordBearer(tokenUrl="/token")

user_viewset.register(
    methods=['LIST', 'GET', 'POST', 'PUT', 'PATCH', 'DELETE'],
    protected_methods=['POST', 'PUT', 'PATCH', 'DELETE'],
    oauth_protect=oauth2
)
```

## Generated Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/users` | List all (paginated) |
| `GET` | `/users/{id}` | Get by ID |
| `POST` | `/users` | Create |
| `PUT` | `/users/{id}` | Replace |
| `PATCH` | `/users/{id}` | Partial update |
| `DELETE` | `/users/{id}` | Delete |

## Supported ORMs & Databases

| ORM | Sync | Async | SQLite | PostgreSQL | MySQL |
|---|---|---|---|---|---|
| SQLAlchemy (default) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Tortoise ORM | — | ✅ | ✅ | ✅ | ✅ |
| Peewee | ✅ | — | ✅ | ✅ | ✅ |

## Configuration (.env)

```env
# SQLAlchemy (default)
ORM_TYPE=sqlalchemy
SQLALCHEMY_DATABASE_URL=sqlite:///./app.db
SQLALCHEMY_ASYNC_DATABASE_URL=sqlite+aiosqlite:///./app.db

# Tortoise ORM
ORM_TYPE=tortoise
TORTOISE_DATABASE_URL=postgresql://user:pass@localhost/db
TORTOISE_MODELS=["app.models"]

# Peewee
ORM_TYPE=peewee
PEEWEE_DATABASE_URL=sqlite:///./app.db
```

## API Reference

### `BaseViewset(endpoint, model, response_model, db_session, tags, allowed_methods?)`

| Parameter | Type | Description |
|---|---|---|
| `endpoint` | `str` | Base URL path, e.g. `/users` |
| `model` | ORM model | SQLAlchemy / Tortoise / Peewee model |
| `response_model` | Pydantic model | Response schema |
| `db_session` | `Callable` | Session factory |
| `tags` | `List[str]` | OpenAPI tags |
| `allowed_methods` | `List[str]` | Whitelist of HTTP methods |

### `register(methods?, oauth_protect?, protected_methods?)`

| Parameter | Description |
|---|---|
| `methods` | Which methods to register (default: all 6) |
| `protected_methods` | Which methods require auth |
| `oauth_protect` | OAuth2 scheme instance |

`AsyncBaseViewset` — same API, all operations are `async`.

## Comparison with Alternatives

| Feature | fastapi-viewsets | fastapi-crudrouter | fastapi-utils |
|---|---|---|---|
| Multi-ORM | ✅ (3 ORMs) | Partial | SQLAlchemy only |
| Async support | ✅ | ✅ | Partial |
| OAuth2 per-method | ✅ | — | — |
| Method selection | ✅ | ✅ | — |
| Pagination | ✅ | ✅ | — |

## Error Handling

- `404 Not Found` — item does not exist
- `400 Bad Request` — validation or database integrity error
- All errors include descriptive messages for easy debugging

## Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change, then submit a PR.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Commit your changes
4. Open a Pull Request

## License

MIT — see [LICENSE](LICENSE)

## Author

**Alexander Valenchits** — [GitHub](https://github.com/svalench)

## Links

- 📦 [PyPI Package](https://pypi.org/project/fastapi-viewsets/)
- 🐛 [Issues](https://github.com/svalench/fastapi_viewsets/issues)
- 📖 [FastAPI docs](https://fastapi.tiangolo.com)
