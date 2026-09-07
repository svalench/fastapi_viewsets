---
hide:
  - navigation
  - toc
---

# fastapi-viewsets

**Django REST Framework-style ViewSets for FastAPI** — auto-generate CRUD endpoints from SQLAlchemy, Tortoise ORM, or Peewee models in minutes.

[![PyPI version](https://badge.fury.io/py/fastapi-viewsets.svg)](https://pypi.org/project/fastapi-viewsets/)
[![Python versions](https://img.shields.io/pypi/pyversions/fastapi-viewsets.svg)](https://pypi.org/project/fastapi-viewsets/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://github.com/svalench/fastapi_viewsets/blob/master/LICENSE)
[![CI](https://github.com/svalench/fastapi_viewsets/actions/workflows/test.yml/badge.svg?branch=master)](https://github.com/svalench/fastapi_viewsets/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/svalench/fastapi_viewsets/graph/badge.svg)](https://codecov.io/gh/svalench/fastapi_viewsets)
[![Downloads/month](https://static.pepy.tech/badge/fastapi-viewsets/month)](https://pepy.tech/project/fastapi-viewsets)

---

## Why fastapi-viewsets

<div class="grid cards" markdown>

- :material-lightning-bolt: **Less boilerplate**

    ---

    Register `LIST`, `GET`, `POST`, `PUT`, `PATCH`, and `DELETE` from one class — no repetitive route definitions.

- :material-database-cog: **ORM-agnostic core**

    ---

    Pluggable adapters for SQLAlchemy (sync & async), Tortoise ORM, and Peewee via `ORM_TYPE` / optional extras.

- :material-shield-check: **Typed & Pydantic-first**

    ---

    OpenAPI tags and response schemas generated from your `response_model`. Full Pydantic v2 support.

- :material-link-variant: **Declarative eager loading**

    ---

    `select_related` / `prefetch_related` via an inner `RelatedConfig` class on Pydantic schemas — eliminates N+1 without touching the viewset.

- :material-page-layout-sidebar-left: **Built-in pagination**

    ---

    `limit` / `offset` on LIST endpoints out of the box.

- :material-lock: **OAuth2 on selected operations**

    ---

    Protect specific CRUD methods with `OAuth2PasswordBearer` via `register()`.

</div>

---

## 30-second example

```python
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String
from typing import Optional

from fastapi_viewsets import BaseViewset
from fastapi_viewsets.db_conf import Base, engine, get_session

app = FastAPI()


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)


class ItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    name: str


Base.metadata.create_all(bind=engine)
items = BaseViewset(
    endpoint="/items",
    model=Item,
    response_model=ItemSchema,
    db_session=get_session,
    tags=["items"],
)
items.register(methods=["LIST", "GET", "POST", "PATCH", "DELETE"])
app.include_router(items)
```

Run it:

```bash
uvicorn main:app --reload
```

That's it — you now have `GET /items`, `GET /items/{id}`, `POST /items`, `PATCH /items/{id}`, and `DELETE /items/{id}` with full OpenAPI docs at `/docs`.

---

## Feature matrix

| Feature | SQLAlchemy (sync) | SQLAlchemy (async) | Tortoise ORM | Peewee |
| --- | --- | --- | --- | --- |
| `BaseViewset` / `AsyncBaseViewset` CRUD | ✅ | ✅ (`AsyncBaseViewset`) | ✅ via adapter + async session | ✅ via adapter |
| `limit` / `offset` on LIST | ✅ | ✅ | ✅ | ✅ |
| OAuth2 on selected methods | ✅ | ✅ | ✅ | ✅ |
| Declarative eager loading | ✅ | ✅ | ✅ (`prefetch_related`) | ✅ (`select_related`) |
| `search` query on LIST | ✅ | ✅ | ✅ | ✅ |
| Declarative ordering / advanced filters | ✅ | ✅ | ✅ | ✅ |

---

## Next steps

- [Getting Started](getting-started.md) — install and run your first viewset
- [Async Quickstart](quickstart-async.md) — `AsyncBaseViewset` with SQLAlchemy 2.x
- [ORM Adapters](orm-adapters.md) — Tortoise and Peewee configuration
- [Eager Loading](eager-loading.md) — eliminate N+1 queries with `RelatedConfig`
