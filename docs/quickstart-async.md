# Async Quickstart (SQLAlchemy 2.x + Pydantic v2)

`AsyncBaseViewset` mirrors `BaseViewset` but every CRUD handler is `async`, backed by an async SQLAlchemy `AsyncSession`.

## Prerequisites

```bash
pip install "fastapi-viewsets[sqlalchemy]" aiosqlite
```

!!! tip "Drivers"

    For production, use `asyncpg` (PostgreSQL) or `aiomysql` (MySQL) instead of `aiosqlite`.

## Configuration

Point `SQLALCHEMY_DATABASE_URL` (or `SQLALCHEMY_ASYNC_DATABASE_URL`) at an async-capable URL. The package auto-converts:

| Sync URL | Async URL |
| --- | --- |
| `sqlite:///` | `sqlite+aiosqlite:///` |
| `postgresql://` | `postgresql+asyncpg://` |
| `mysql://` | `mysql+aiomysql://` |

Create a `.env`:

```dotenv
ORM_TYPE=sqlalchemy
SQLALCHEMY_DATABASE_URL=sqlite:///./test.db
# Async URL auto-derived; or set explicitly:
# SQLALCHEMY_ASYNC_DATABASE_URL=sqlite+aiosqlite:///./test.db
```

## Full example

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String
from typing import Optional

from fastapi_viewsets import AsyncBaseViewset
from fastapi_viewsets.db_conf import (
    Base,
    async_engine,
    get_async_session,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables once on startup using the async engine.
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(lifespan=lifespan)


class Item(Base):
    """Async-friendly SQLAlchemy model."""

    __tablename__ = "items_async"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)


class ItemSchema(BaseModel):
    """Pydantic v2 schema reused as request and response model."""

    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    name: str



items = AsyncBaseViewset(
    endpoint="/items",
    model=Item,
    response_model=ItemSchema,
    db_session=get_async_session,
    tags=["items"],
)
items.register(methods=["LIST", "GET", "POST", "PATCH", "DELETE"])
app.include_router(items)
```

## Key differences from sync

| Aspect | `BaseViewset` (sync) | `AsyncBaseViewset` (async) |
| --- | --- | --- |
| Handler signature | `def list(...)` | `async def list(...)` |
| Session type | `Session` | `AsyncSession` |
| Session factory | `get_session` | `get_async_session` |
| Table creation | `Base.metadata.create_all(bind=engine)` | `await conn.run_sync(Base.metadata.create_all)` |
| PATCH semantics | `model_dump(exclude_unset=True)` | Same — unset fields preserved |

## Notes

- **Pydantic v2 is required** (`pydantic>=2.5`). Use `model_config = ConfigDict(from_attributes=True)` instead of the v1 `class Config: orm_mode = True`.
- **PATCH** uses `model_dump(exclude_unset=True)` internally, so unset fields are not overwritten with defaults.
- **Missing async driver**: if `aiosqlite` / `asyncpg` / `aiomysql` is not installed, sync usage still works — only `get_async_session()` raises a helpful `RuntimeError` (since v1.2.1).
- **MSSQL**: for SQL Server, set the async URL explicitly via `SQLALCHEMY_ASYNC_DATABASE_URL` using `mssql+aioodbc://...`.

## Next steps

- [Eager Loading](eager-loading.md) — eliminate N+1 queries with `RelatedConfig`
- [Overriding Handlers](overrides.md) — custom search, ordering, and conflict handling
- [ORM Adapters](orm-adapters.md) — Tortoise and Peewee setup
