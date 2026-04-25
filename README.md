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
