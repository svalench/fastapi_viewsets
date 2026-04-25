# fastapi-viewsets

Django REST Framework-style ViewSets for FastAPI — auto-generate CRUD endpoints from SQLAlchemy, Tortoise ORM, or Peewee models in minutes.

[![PyPI version](https://badge.fury.io/py/fastapi-viewsets.svg)](https://pypi.org/project/fastapi-viewsets/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-viewsets.svg)](https://pypi.org/project/fastapi-viewsets/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/svalench/fastapi_viewsets/blob/main/LICENSE)
[![CI](https://github.com/svalench/fastapi_viewsets/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/svalench/fastapi_viewsets/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/svalench/fastapi_viewsets/graph/badge.svg)](https://codecov.io/gh/svalench/fastapi_viewsets)
[![Downloads/month](https://static.pepy.tech/badge/fastapi-viewsets/month)](https://pepy.tech/project/fastapi-viewsets)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](https://github.com/svalench/fastapi_viewsets/pulls)

## Why fastapi-viewsets

- **DRF-style ergonomics** on top of FastAPI routers and dependency injection.
- **Less boilerplate** — register LIST, GET, POST, PUT, PATCH, and DELETE from one class.
- **ORM-agnostic core** — pluggable adapters for SQLAlchemy (sync/async), Tortoise ORM, and Peewee (`ORM_TYPE` / optional extras).
- **Typed, Pydantic-first responses** with OpenAPI tags and schemas generated from your `response_model`.
- **Built-in list pagination** (`limit` / `offset`), optional OAuth2 on selected operations, and room to grow for search and richer filters (see Roadmap).

## Feature matrix

| Feature | SQLAlchemy (sync) | SQLAlchemy (async) | Tortoise ORM | Peewee |
| --- | --- | --- | --- | --- |
| `BaseViewset` / `AsyncBaseViewset` CRUD | Supported | Supported (`AsyncBaseViewset`) | Supported via adapter + async session | Supported via adapter |
| `limit` / `offset` on LIST | Supported | Supported | Supported | Supported |
| OAuth2 on selected methods (`register`) | Supported | Supported | Supported | Supported |
| `search` query on LIST (server-side) | **Roadmap** | **Roadmap** | **Roadmap** | **Roadmap** |
| Declarative ordering / advanced filters | **Roadmap** | **Roadmap** | **Roadmap** | **Roadmap** |

## Installation

```bash
pip install fastapi-viewsets
```

Optional extras (see `setup.py`):

```bash
pip install "fastapi-viewsets[sqlalchemy]"
pip install "fastapi-viewsets[tortoise]"
pip install "fastapi-viewsets[peewee]"
pip install "fastapi-viewsets[test]"   # pytest, httpx, coverage, etc.
```

For async SQLAlchemy you still need a driver such as `aiosqlite`, `asyncpg`, or `aiomysql` alongside your database URL.

## Database connection examples

`fastapi-viewsets` doesn't bundle DB drivers — you pick them per stack.
The table below maps each ORM to the install command, the driver(s)
you need, and the URL shape for **PostgreSQL**, **MySQL**, and
**Microsoft SQL Server**.

| ORM | PostgreSQL | MySQL | MSSQL |
| --- | --- | --- | --- |
| **SQLAlchemy (sync)** | `psycopg[binary]` or `psycopg2-binary` | `pymysql` or `mysqlclient` | `pyodbc` + ODBC Driver 17/18 |
| **SQLAlchemy (async)** | `asyncpg` | `aiomysql` or `asyncmy` | `aioodbc` + ODBC Driver 17/18 |
| **Tortoise ORM** | `asyncpg` (built-in) | `aiomysql` (built-in) | Not supported by Tortoise |
| **Peewee** | `psycopg2-binary` | `pymysql` or `mysqlclient` | Not supported by this adapter |

> The `SQLAlchemyAdapter` auto-converts a sync URL to its async
> counterpart (`postgresql://` → `postgresql+asyncpg://`,
> `mysql://` → `mysql+aiomysql://`, `sqlite:///` →
> `sqlite+aiosqlite:///`). For MSSQL you have to set the async URL
> explicitly via `SQLALCHEMY_ASYNC_DATABASE_URL`. If the matching async
> driver is not installed, `SQLAlchemyAdapter` falls back to sync-only
> mode and `get_async_session()` raises a helpful `RuntimeError`
> (since v1.2.1).

The library reads database configuration from environment variables
(loaded via `python-dotenv` from `.env`). Pick the ORM with `ORM_TYPE`,
then set the URL with `<ORM>_DATABASE_URL` (or the generic
`DATABASE_URL`).

### SQLAlchemy (sync and async)

```bash
# PostgreSQL
pip install "fastapi-viewsets[sqlalchemy]" "psycopg[binary]" asyncpg

# MySQL
pip install "fastapi-viewsets[sqlalchemy]" pymysql aiomysql

# MSSQL (needs Microsoft ODBC Driver 17 or 18 on the host)
pip install "fastapi-viewsets[sqlalchemy]" pyodbc aioodbc
```

Example `.env` (one block at a time):

```dotenv
# --- PostgreSQL ---
ORM_TYPE=sqlalchemy
SQLALCHEMY_DATABASE_URL=postgresql+psycopg://user:pass@db.example.com:5432/app
# Optional explicit async URL; otherwise auto-derived to postgresql+asyncpg://
SQLALCHEMY_ASYNC_DATABASE_URL=postgresql+asyncpg://user:pass@db.example.com:5432/app

# --- MySQL ---
ORM_TYPE=sqlalchemy
SQLALCHEMY_DATABASE_URL=mysql+pymysql://user:pass@db.example.com:3306/app?charset=utf8mb4
SQLALCHEMY_ASYNC_DATABASE_URL=mysql+aiomysql://user:pass@db.example.com:3306/app?charset=utf8mb4

# --- MSSQL ---
ORM_TYPE=sqlalchemy
# URL-encode the ODBC driver name ("+" instead of spaces).
SQLALCHEMY_DATABASE_URL=mssql+pyodbc://user:pass@db.example.com:1433/app?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
SQLALCHEMY_ASYNC_DATABASE_URL=mssql+aioodbc://user:pass@db.example.com:1433/app?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

Use `BaseViewset` for sync code or `AsyncBaseViewset` for async code
(see the [Async quickstart](#async-quickstart-sqlalchemy-2x--pydantic-v2)
below).

### Tortoise ORM

Tortoise is async-only. The adapter takes a database URL plus a list
of model modules to register on startup.

```bash
# PostgreSQL
pip install "fastapi-viewsets[tortoise]"          # pulls in asyncpg

# MySQL
pip install "fastapi-viewsets[tortoise]" aiomysql
```

```dotenv
# --- PostgreSQL ---
ORM_TYPE=tortoise
TORTOISE_DATABASE_URL=postgres://user:pass@db.example.com:5432/app
TORTOISE_MODELS=["app.models"]
TORTOISE_APP_LABEL=models

# --- MySQL ---
ORM_TYPE=tortoise
TORTOISE_DATABASE_URL=mysql://user:pass@db.example.com:3306/app
TORTOISE_MODELS=["app.models"]
TORTOISE_APP_LABEL=models
```

```python
from fastapi import FastAPI
from tortoise import Tortoise

from fastapi_viewsets import AsyncBaseViewset
from fastapi_viewsets.orm.factory import ORMFactory

app = FastAPI()
adapter = ORMFactory.get_default_adapter()  # built from the env vars above


@app.on_event("startup")
async def _init_tortoise() -> None:
    """Open the Tortoise connection pool and create schema if needed.

    The adapter also initializes Tortoise lazily on first DB call;
    doing it here gives you control over schema creation.
    """
    await Tortoise.init(
        db_url=adapter.database_url,
        modules={adapter.app_label: adapter.models},
    )
    await Tortoise.generate_schemas(safe=True)


@app.on_event("shutdown")
async def _close_tortoise() -> None:
    """Close the Tortoise connection pool."""
    await Tortoise.close_connections()


# Define your Tortoise models in app/models.py and pass them to AsyncBaseViewset.
# from app.models import Item
# from app.schemas import ItemSchema
# items = AsyncBaseViewset(
#     endpoint="/items",
#     model=Item,
#     response_model=ItemSchema,
#     db_session=adapter.get_async_session,
#     orm_adapter=adapter,
#     tags=["items"],
# )
# items.register(methods=["LIST", "GET", "POST", "PATCH", "DELETE"])
# app.include_router(items)
```

> **MSSQL is not supported by Tortoise ORM.** Use SQLAlchemy with
> `aioodbc` for SQL Server.

### Peewee

Peewee is sync-only. The adapter parses the URL and instantiates the
right `Database` class.

```bash
# PostgreSQL
pip install "fastapi-viewsets[peewee]" psycopg2-binary

# MySQL
pip install "fastapi-viewsets[peewee]" pymysql
```

```dotenv
# --- PostgreSQL ---
ORM_TYPE=peewee
PEEWEE_DATABASE_URL=postgresql://user:pass@db.example.com:5432/app

# --- MySQL ---
ORM_TYPE=peewee
PEEWEE_DATABASE_URL=mysql://user:pass@db.example.com:3306/app
```

```python
from fastapi import FastAPI

from fastapi_viewsets import BaseViewset
from fastapi_viewsets.orm.factory import ORMFactory

app = FastAPI()
adapter = ORMFactory.get_default_adapter()  # built from the env vars above

# from app.models import Item            # peewee.Model subclass
# from app.schemas import ItemSchema     # Pydantic v2 schema
# items = BaseViewset(
#     endpoint="/items",
#     model=Item,
#     response_model=ItemSchema,
#     db_session=adapter.get_session,
#     orm_adapter=adapter,
#     tags=["items"],
# )
# items.register(methods=["LIST", "GET", "POST", "PATCH", "DELETE"])
# app.include_router(items)
```

> **MSSQL is not supported by this Peewee adapter** (the URL parser
> only handles `sqlite:///`, `postgresql://`, `postgres://`,
> `mysql://`). For SQL Server, use SQLAlchemy.

### Building the adapter from code (no env vars)

When you don't want to rely on environment variables, instantiate the
adapter directly and pass it to the viewset via `orm_adapter=`:

```python
from fastapi_viewsets.orm.factory import ORMFactory

adapter = ORMFactory.create_adapter(
    "sqlalchemy",
    {
        "database_url": "postgresql+psycopg://user:pass@db.example.com:5432/app",
        "async_database_url": "postgresql+asyncpg://user:pass@db.example.com:5432/app",
    },
)
```

## Quickstart (SQLAlchemy, sync)

Save as `main.py` in an empty folder and run `python main.py` or `uvicorn main:app --reload`.

```python
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String

from fastapi_viewsets import BaseViewset
from fastapi_viewsets.db_conf import Base, engine, get_session

app = FastAPI()


class Item(Base):
    """Example SQLAlchemy model."""

    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)


class ItemSchema(BaseModel):
    """Pydantic model for request and response bodies."""

    model_config = ConfigDict(from_attributes=True)
    id: int | None = None
    name: str


Base.metadata.create_all(bind=engine)
items = BaseViewset(endpoint="/items", model=Item, response_model=ItemSchema, db_session=get_session, tags=["items"])
items.register(methods=["LIST", "GET", "POST", "PATCH", "DELETE"])
app.include_router(items)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
```

`GET /items` returns `200` with a JSON list (possibly empty). Use `POST /items` with `{"name": "apple"}` to create rows.

## Async quickstart (SQLAlchemy 2.x + Pydantic v2)

`AsyncBaseViewset` mirrors `BaseViewset` but every CRUD handler is
`async`, backed by an async SQLAlchemy `AsyncSession`. Install an async
driver alongside the package:

```bash
pip install "fastapi-viewsets[sqlalchemy]" aiosqlite
```

Point `SQLALCHEMY_DATABASE_URL` (or `SQLALCHEMY_ASYNC_DATABASE_URL`) at
an async-capable URL and use the lazy helpers from `db_conf`. The
package auto-converts `sqlite://` to `sqlite+aiosqlite://`,
`postgresql://` to `postgresql+asyncpg://`, etc.

```python
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String

from fastapi_viewsets import AsyncBaseViewset
from fastapi_viewsets.db_conf import (
    Base,
    async_engine,
    get_async_session,
)

app = FastAPI()


class Item(Base):
    """Async-friendly SQLAlchemy model."""

    __tablename__ = "items_async"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)


class ItemSchema(BaseModel):
    """Pydantic v2 schema reused as request and response model."""

    model_config = ConfigDict(from_attributes=True)
    id: int | None = None
    name: str


@app.on_event("startup")
async def _create_tables() -> None:
    """Create tables once on startup using the async engine."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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

Notes:

- Pydantic v2 is required (`pydantic>=2.5`). Use
  `model_config = ConfigDict(from_attributes=True)` instead of the v1
  `class Config: orm_mode = True`.
- `PATCH` uses `model_dump(exclude_unset=True)` internally, so unset
  fields are no longer overwritten with defaults.
- If the async driver (`aiosqlite` / `asyncpg` / `aiomysql`) is not
  installed, sync usage still works — only `get_async_session()` raises
  a helpful `RuntimeError`.

## Overriding `list` and `create_element` (custom LIST and POST)

Every CRUD handler is a regular method, so subclassing the viewset is
the canonical way to add filtering, ordering, validation, conflict
handling, and so on. The example below subclasses `AsyncBaseViewset`
and overrides both `list` (case-insensitive search + simple ordering)
and `create_element` (input normalization + map `IntegrityError` to
409).

```python
from typing import List, Optional

from fastapi import Body, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Column, DateTime, Integer, String, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from fastapi_viewsets import AsyncBaseViewset
from fastapi_viewsets.db_conf import Base, get_async_session


class Item(Base):
    """Item model with timestamps and a unique name."""

    __tablename__ = "items_custom"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True, index=True)
    description = Column(String(1024), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ItemSchema(BaseModel):
    """Single Pydantic v2 schema reused as request and response model.

    Server-controlled fields (``id``, ``created_at``) are optional so
    the same schema can be used for POST/PATCH bodies and responses
    — ``register()`` patches the body annotation to ``response_model``.
    """

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1024)
    created_at: Optional[object] = None  # datetime in real code


class ItemsViewSet(AsyncBaseViewset):
    """Custom async viewset that overrides LIST and POST."""

    async def list(  # type: ignore[override]
        self,
        limit: int = 20,
        offset: int = 0,
        search: Optional[str] = None,
        order_by: str = "-created_at",
        token: Optional[str] = None,
    ) -> List[ItemSchema]:
        """Custom LIST: case-insensitive search + whitelist ordering.

        Query: ``GET /items?search=foo&order_by=-name&limit=10``.
        """
        session: AsyncSession = self.db_session()
        try:
            stmt = select(self.model)
            if search:
                stmt = stmt.where(self.model.name.ilike(f"%{search}%"))

            # "-name" → desc, "name" → asc; whitelist allowed columns.
            field, desc = (order_by[1:], True) if order_by.startswith("-") else (order_by, False)
            column = {"name": self.model.name, "created_at": self.model.created_at}.get(field)
            if column is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported order_by")
            stmt = stmt.order_by(column.desc() if desc else column.asc())
            stmt = stmt.offset(offset).limit(limit)

            rows = (await session.execute(stmt)).scalars().all()
            return [ItemSchema.model_validate(row) for row in rows]
        finally:
            await session.close()

    async def create_element(  # type: ignore[override]
        self,
        item: ItemSchema = Body(...),
        token: Optional[str] = None,
    ) -> ItemSchema:
        """Custom POST: normalize, persist, map IntegrityError to 409."""
        # Pydantic v2 dump; ``str_strip_whitespace`` already trimmed strings.
        payload = item.model_dump(exclude_unset=True, exclude={"id", "created_at"})

        session: AsyncSession = self.db_session()
        try:
            obj = self.model(**payload)
            session.add(obj)
            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"Item '{payload.get('name')}' already exists",
                ) from exc
            await session.refresh(obj)
            return ItemSchema.model_validate(obj)
        finally:
            await session.close()


items = ItemsViewSet(
    endpoint="/items",
    model=Item,
    response_model=ItemSchema,
    db_session=get_async_session,
    tags=["items"],
)
items.register(methods=["LIST", "GET", "POST", "PATCH", "DELETE"])
```

Key points when overriding:

- **Keep the method names and the `item` body parameter.** `register()`
  introspects `list`, `get_element`, `create_element`,
  `update_element`, `delete_element`. It also rewrites the
  ``item.__annotation__`` to `response_model` so the OpenAPI body
  schema stays consistent — use the same schema for request and
  response, or pre-validate inside the handler.
- **Adding new query parameters is fine** (`search`, `order_by`,
  filters, etc.); FastAPI picks them up automatically.
- **Manage your own session lifecycle** in overrides (`try/finally` +
  `await session.close()`) or use a FastAPI dependency with `yield`.
- For sync apps, the same pattern applies to `BaseViewset` — just drop
  the `async`/`await` and use `Session` instead of `AsyncSession`.

## Authentication example

`register()` accepts `OAuth2PasswordBearer` plus a list of logical operations (`POST`, `PUT`, …) that require a bearer token.

```python
from fastapi import FastAPI
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String
from fastapi_viewsets import BaseViewset
from fastapi_viewsets.db_conf import Base, engine, get_session

app = FastAPI()
oauth2 = OAuth2PasswordBearer(tokenUrl="/token")

class Item(Base):
    """SQLAlchemy model for OAuth2-protected writes."""

    __tablename__ = "items_oauth"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)


class ItemSchema(BaseModel):
    """Pydantic schema for Item payloads and responses."""

    model_config = ConfigDict(from_attributes=True)
    id: int | None = None
    name: str


Base.metadata.create_all(bind=engine)
router = BaseViewset(endpoint="/items", model=Item, response_model=ItemSchema, db_session=get_session, tags=["items"])
router.register(methods=["LIST", "GET", "POST", "PATCH", "DELETE"], oauth_protect=oauth2, protected_methods=["POST", "PATCH", "DELETE"])
app.include_router(router)
```

## Pagination, filtering, ordering

**Pagination** — `BaseViewset.list` maps `limit` and `offset` to query parameters on the LIST route.

```python
from fastapi_viewsets import BaseViewset

def pagination_hint() -> str:
    """Document LIST pagination after `register()` (e.g. GET /items?limit=10&offset=20)."""
    return "limit and offset are parsed by `BaseViewset.list`"
```

**Filtering** — `list` accepts `search`, but ORM adapters ignore it today; server-side search is on the Roadmap. Subclass `BaseViewset` and override `list()` with your own query until then.

```python
from fastapi_viewsets import BaseViewset

def filtering_hint() -> str:
    """Explain that `search` is reserved; override `list` for real filters today."""
    return "search parameter is not yet applied in adapters"
```

**Ordering** — there is no shared `order_by` helper yet; override `list()` with an ordered query or wait for the Roadmap.

```python
from fastapi_viewsets import BaseViewset

def ordering_hint() -> str:
    """Note the absence of a built-in ordering helper on LIST endpoints."""
    return "override list or wait for roadmap ordering helpers"
```

## Permissions and custom routes

There is no `get_queryset` hook; scope queries by subclassing `BaseViewset` and overriding `list()`, `get_element()`, or related handlers. The class subclasses `APIRouter`, so attach extra endpoints with `add_api_route` **before** `register()` if paths must win over `/{id}`:

```python
from fastapi_viewsets import BaseViewset


class ItemsWithStats(BaseViewset):
    """Adds a custom read-only route alongside generated CRUD."""

    def __init__(self, *args, **kwargs):
        """Register static paths before CRUD routes."""
        super().__init__(*args, **kwargs)
        self.add_api_route(
            f"{self.endpoint}/stats",
            self.collection_stats,
            methods=["GET"],
            tags=self.tags or [],
            name="items_stats",
        )

    def collection_stats(self) -> dict[str, str]:
        """Return a minimal summary for monitoring or health checks."""
        return {"resource": self.endpoint.strip("/")}


# Instantiate with model, response_model, and db_session (see quickstart), then call register().
```

## What is new (v1.2.0)

- Pydantic v2 first: CRUD handlers use `model_dump(exclude_unset=...)`, fixing PATCH semantics that previously overwrote unset fields with defaults.
- Lazy `db_conf`: importing the package no longer creates SQLAlchemy engines unless they are needed, and works without async drivers installed.
- Single source of truth for sync→async URL conversion and the default adapter singleton.
- Internal `register()` deduplicated between sync and async viewsets via a shared mixin.
- PEP 621 `pyproject.toml`, `python_requires>=3.9`, FastAPI `>=0.110`, ruff/black/mypy preconfigured.

Previous release: [v1.1.0](RELEASE_1.1.0.md) introduced multi-ORM support via adapters (SQLAlchemy default, optional Tortoise and Peewee), `ORMFactory` and environment-driven `ORM_TYPE` configuration.

Details: [RELEASE_NOTES.md](RELEASE_NOTES.md), [RELEASE_1.2.0.md](RELEASE_1.2.0.md), [RELEASE_1.1.0.md](RELEASE_1.1.0.md).

## Roadmap (planned)

| Item | Target | Status |
| --- | --- | --- |
| Dedicated `AsyncModelViewSet` ergonomics on top of SQLAlchemy 2.x async sessions | v1.2 | Planned |
| First-class Tortoise ORM viewset examples and docs (`TortoiseModelViewSet` naming TBD) | v1.2 | Planned |
| Async pagination helpers and transaction boundaries across adapters | v1.3 | Planned |
| Richer OpenAPI for nested Pydantic models | v1.3 | Planned |
| Wire `search` on LIST to real database queries | v1.2 | Planned |

## Comparison with alternatives

| Approach | Developer experience | ORM support | Permissions | Filtering |
| --- | --- | --- | --- | --- |
| fastapi-viewsets | One `BaseViewset` registers CRUD routes | SQLAlchemy sync/async, Tortoise, Peewee via adapters | OAuth2 per logical method via `register` | `limit`/`offset` today; `search` and advanced filters on Roadmap |
| fastapi-crudrouter | CRUD-focused generators, less ViewSet-shaped | Primarily SQLAlchemy | Custom middleware/deps | Often extended manually |
| Hand-rolled FastAPI | Full control, most boilerplate | Any ORM you integrate | Fully custom | Fully custom |

## Testing

From the repository root (see `pytest.ini`):

```bash
pytest
```

Coverage is enforced with `--cov-fail-under=70` (HTML and XML reports are emitted for local inspection).

## Contributing

See [open issues](https://github.com/svalench/fastapi_viewsets/issues) to propose changes; pull requests are welcome.

## License

Distributed under the MIT License. See [LICENSE](LICENSE).

## Author

Built by [Alexander Valenchits](https://github.com/svalench) — Tech Lead @ AluSoft, Minsk.
