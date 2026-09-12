# Installation

## Requirements

| Dependency | Version |
| --- | --- |
| Python | >= 3.9 |
| FastAPI | >= 0.110 |
| Pydantic | >= 2.5, < 3 |
| python-dotenv | >= 0.19 |
| SQLAlchemy | >= 2.0.0 (only for the `sqlalchemy` extra / default `ORM_TYPE`) |

## Install from PyPI

```bash
pip install fastapi-viewsets
```

## Optional extras

The base install is ORM-agnostic (FastAPI + Pydantic + python-dotenv only).
Add the extra for your ORM — and an ASGI server such as `uvicorn` to run
your app:

=== "SQLAlchemy"

    ```bash
    pip install "fastapi-viewsets[sqlalchemy]"
    ```

    For async SQLAlchemy, also install a driver:

    ```bash
    pip install aiosqlite          # SQLite (development)
    pip install asyncpg            # PostgreSQL
    pip install aiomysql            # MySQL
    ```

=== "Tortoise ORM"

    ```bash
    pip install "fastapi-viewsets[tortoise]"   # pulls in asyncpg
    ```

    For MySQL with Tortoise:

    ```bash
    pip install "fastapi-viewsets[tortoise]" aiomysql
    ```

=== "Peewee"

    ```bash
    pip install "fastapi-viewsets[peewee]"

    # PostgreSQL driver
    pip install psycopg2-binary

    # MySQL driver
    pip install pymysql
    ```

=== "Test dependencies"

    ```bash
    pip install "fastapi-viewsets[test]"
    ```

    Includes `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`, `faker`, and `aiosqlite`.

## Install from source (development)

```bash
git clone https://github.com/svalench/fastapi_viewsets.git
cd fastapi_viewsets
pip install -e ".[test,lint]"
```

## Verifying the installation

```bash
python -c "from fastapi_viewsets import BaseViewset, AsyncBaseViewset; print('OK')"
```

If this prints `OK`, you're ready to go.

## What's next

- [Sync Quickstart](quickstart-sync.md) — a complete CRUD app in ~25 lines
- [Async Quickstart](quickstart-async.md) — `AsyncBaseViewset` with async SQLAlchemy
- [ORM Adapters](orm-adapters.md) — configuring Tortoise or Peewee
