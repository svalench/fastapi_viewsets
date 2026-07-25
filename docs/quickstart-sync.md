# Sync Quickstart (SQLAlchemy)

This guide walks through a complete CRUD API using `BaseViewset` with synchronous SQLAlchemy.

!!! info "Prerequisites"

    ```bash
    pip install "fastapi-viewsets[sqlalchemy]"
    ```

## Full example

Save as `main.py` in an empty folder and run `python main.py` or `uvicorn main:app --reload`:

```python
from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Integer, String
from typing import Optional

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

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
```

## What just happened

1. **Model** — `Item` is a standard SQLAlchemy declarative model. It inherits from `Base`, which is the lazy SQLAlchemy declarative base provided by `fastapi_viewsets.db_conf`.

2. **Schema** — `ItemSchema` is a Pydantic v2 model with `model_config = ConfigDict(from_attributes=True)`. This enables `model_validate()` to read directly from ORM objects (replacing the old v1 `class Config: orm_mode = True`).

3. **Viewset** — `BaseViewset` is instantiated with:
    - `endpoint` — the base URL path (`"/items"`)
    - `model` — the SQLAlchemy model class
    - `response_model` — the Pydantic schema (used for both request bodies and responses)
    - `db_session` — a session factory (here, `get_session` from `db_conf`)
    - `tags` — OpenAPI tag grouping

4. **Register** — `register()` wires the CRUD routes. Pass a list of logical methods:

    | Method | HTTP | Path | Description |
    | --- | --- | --- | --- |
    | `LIST` | `GET` | `/items` | List with `limit` / `offset` |
    | `GET` | `GET` | `/items/{id}` | Retrieve single item |
    | `POST` | `POST` | `/items` | Create item |
    | `PUT` | `PUT` | `/items/{id}` | Full update |
    | `PATCH` | `PATCH` | `/items/{id}` | Partial update (only set fields) |
    | `DELETE` | `DELETE` | `/items/{id}` | Delete item |

5. **Router** — `app.include_router(items)` mounts the viewset (which subclasses `APIRouter`) on the FastAPI app.

## Testing the endpoints

Start the server:

```bash
uvicorn main:app --reload
```

Create an item:

```bash
curl -X POST http://127.0.0.1:8000/items \
  -H "Content-Type: application/json" \
  -d '{"name": "apple"}'
# {"id":1,"name":"apple"}
```

List items:

```bash
curl http://127.0.0.1:8000/items
# [{"id":1,"name":"apple"}]

curl "http://127.0.0.1:8000/items?limit=10&offset=0"
```

Get a single item:

```bash
curl http://127.0.0.1:8000/items/1
# {"id":1,"name":"apple"}
```

Patch an item:

```bash
curl -X PATCH http://127.0.0.1:8000/items/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "banana"}'
# {"id":1,"name":"banana"}
```

Delete an item:

```bash
curl -X DELETE http://127.0.0.1:8000/items/1
# {"status":true,"text":"successfully deleted"}
```

Interactive API docs are available at `http://127.0.0.1:8000/docs`.

## Environment configuration

By default, `db_conf` falls back to `sqlite:///<cwd>/base.db`. To use a real database, create a `.env` file:

```dotenv
ORM_TYPE=sqlalchemy
SQLALCHEMY_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/mydb
```

See [ORM Adapters](orm-adapters.md) for all supported databases and drivers.

## Next steps

- [Async Quickstart](quickstart-async.md) — async version with `AsyncBaseViewset`
- [Overriding Handlers](overrides.md) — custom search, ordering, and error handling
- [Authentication](authentication.md) — protecting endpoints with OAuth2
