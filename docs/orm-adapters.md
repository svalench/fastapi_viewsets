# ORM Adapters

`fastapi-viewsets` doesn't bundle database drivers — you pick them per stack. The library reads configuration from environment variables (loaded via `python-dotenv` from `.env`). Pick the ORM with `ORM_TYPE`, then set the URL with `<ORM>_DATABASE_URL` (or the generic `DATABASE_URL`).

## Supported ORMs

| ORM | Sync | Async | Extra |
| --- | --- | --- | --- |
| SQLAlchemy | ✅ `BaseViewset` | ✅ `AsyncBaseViewset` | `[sqlalchemy]` |
| Tortoise ORM | — | ✅ `AsyncBaseViewset` | `[tortoise]` |
| Peewee | ✅ `BaseViewset` | — | `[peewee]` |

## Database driver matrix

| ORM | PostgreSQL | MySQL | MSSQL |
| --- | --- | --- | --- |
| **SQLAlchemy (sync)** | `psycopg[binary]` or `psycopg2-binary` | `pymysql` or `mysqlclient` | `pyodbc` + ODBC Driver 17/18 |
| **SQLAlchemy (async)** | `asyncpg` | `aiomysql` or `asyncmy` | `aioodbc` + ODBC Driver 17/18 |
| **Tortoise ORM** | `asyncpg` (built-in) | `aiomysql` (built-in) | Not supported by Tortoise |
| **Peewee** | `psycopg2-binary` | `pymysql` or `mysqlclient` | Not supported by this adapter |

!!! note "Auto sync-to-async URL conversion"

    The `SQLAlchemyAdapter` auto-converts a sync URL to its async counterpart:

    - `postgresql://` → `postgresql+asyncpg://`
    - `mysql://` → `mysql+aiomysql://`
    - `sqlite:///` → `sqlite+aiosqlite:///`

    For MSSQL you must set the async URL explicitly via `SQLALCHEMY_ASYNC_DATABASE_URL`. If the matching async driver is not installed, `SQLAlchemyAdapter` falls back to sync-only mode and `get_async_session()` raises a helpful `RuntimeError` (since v1.2.1).

---

## SQLAlchemy (sync and async)

### PostgreSQL

```bash
pip install "fastapi-viewsets[sqlalchemy]" "psycopg[binary]" asyncpg
```

### MySQL

```bash
pip install "fastapi-viewsets[sqlalchemy]" pymysql aiomysql
```

### MSSQL

Requires Microsoft ODBC Driver 17 or 18 on the host:

```bash
pip install "fastapi-viewsets[sqlalchemy]" pyodbc aioodbc
```

### `.env` examples

=== "PostgreSQL"

    ```dotenv
    ORM_TYPE=sqlalchemy
    SQLALCHEMY_DATABASE_URL=postgresql+psycopg://user:pass@db.example.com:5432/app
    # Optional explicit async URL; otherwise auto-derived to postgresql+asyncpg://
    SQLALCHEMY_ASYNC_DATABASE_URL=postgresql+asyncpg://user:pass@db.example.com:5432/app
    ```

=== "MySQL"

    ```dotenv
    ORM_TYPE=sqlalchemy
    SQLALCHEMY_DATABASE_URL=mysql+pymysql://user:pass@db.example.com:3306/app?charset=utf8mb4
    SQLALCHEMY_ASYNC_DATABASE_URL=mysql+aiomysql://user:pass@db.example.com:3306/app?charset=utf8mb4
    ```

=== "MSSQL"

    ```dotenv
    ORM_TYPE=sqlalchemy
    # URL-encode the ODBC driver name ("+" instead of spaces).
    SQLALCHEMY_DATABASE_URL=mssql+pyodbc://user:pass@db.example.com:1433/app?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
    SQLALCHEMY_ASYNC_DATABASE_URL=mssql+aioodbc://user:pass@db.example.com:1433/app?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
    ```

Use `BaseViewset` for sync code or `AsyncBaseViewset` for async code — see [Sync Quickstart](quickstart-sync.md) and [Async Quickstart](quickstart-async.md).

---

## Tortoise ORM

Tortoise is async-only. The adapter takes a database URL plus a list of model modules to register on startup.

```bash
# PostgreSQL
pip install "fastapi-viewsets[tortoise]"          # pulls in asyncpg

# MySQL
pip install "fastapi-viewsets[tortoise]" aiomysql
```

### `.env` examples

=== "PostgreSQL"

    ```dotenv
    ORM_TYPE=tortoise
    TORTOISE_DATABASE_URL=postgres://user:pass@db.example.com:5432/app
    TORTOISE_MODELS=["app.models"]
    TORTOISE_APP_LABEL=models
    ```

=== "MySQL"

    ```dotenv
    ORM_TYPE=tortoise
    TORTOISE_DATABASE_URL=mysql://user:pass@db.example.com:3306/app
    TORTOISE_MODELS=["app.models"]
    TORTOISE_APP_LABEL=models
    ```

### Usage

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

!!! warning "MSSQL not supported"

    MSSQL is not supported by Tortoise ORM. Use SQLAlchemy with `aioodbc` for SQL Server.

---

## Peewee

Peewee is sync-only. The adapter parses the URL and instantiates the right `Database` class.

```bash
# PostgreSQL
pip install "fastapi-viewsets[peewee]" psycopg2-binary

# MySQL
pip install "fastapi-viewsets[peewee]" pymysql
```

### `.env` examples

=== "PostgreSQL"

    ```dotenv
    ORM_TYPE=peewee
    PEEWEE_DATABASE_URL=postgresql://user:pass@db.example.com:5432/app
    ```

=== "MySQL"

    ```dotenv
    ORM_TYPE=peewee
    PEEWEE_DATABASE_URL=mysql://user:pass@db.example.com:3306/app
    ```

### Usage

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

!!! warning "MSSQL not supported"

    The Peewee adapter only handles `sqlite:///`, `postgresql://`, `postgres://`, and `mysql://`. For SQL Server, use SQLAlchemy.

---

## Building the adapter from code (no env vars)

When you don't want to rely on environment variables, instantiate the adapter directly and pass it to the viewset via `orm_adapter=`:

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

This is useful for testing, multi-tenant setups, or when configuration comes from a secrets manager rather than `.env`.

## The `ORMFactory` class

The `ORMFactory` is the central entry point for adapter resolution:

| Method | Returns | Description |
| --- | --- | --- |
| `ORMFactory.get_default_adapter()` | `BaseORMAdapter` | Returns the cached singleton adapter for the current `ORM_TYPE` |
| `ORMFactory.create_adapter(orm_type, config)` | `BaseORMAdapter` | Creates a new adapter instance from a dict config |

All adapters implement the `BaseORMAdapter` abstract interface — see [API Reference](api-reference.md) for the full method list.
