# API Reference

## `BaseViewset`

```python
from fastapi_viewsets import BaseViewset
```

Synchronous CRUD viewset. Subclasses `APIRouter` and `_RegisterMixin`. Provides `LIST`, `GET`, `POST`, `PUT`, `PATCH`, and `DELETE` endpoints generated from an ORM model and a Pydantic response model.

### Constructor

```python
BaseViewset(
    *,
    allowed_methods: Optional[List[str]] = None,
    endpoint: Optional[str] = None,
    model: Optional[Type[ModelType]] = None,
    db_session: Optional[Callable[[], Any]] = None,
    response_model: Optional[Type[BaseModel]] = None,
    orm_adapter: Optional[BaseORMAdapter] = None,
    **kwargs,  # forwarded to APIRouter
)
```

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `allowed_methods` | `Optional[List[str]]` | `None` | Override of `ALLOWED_METHODS` |
| `endpoint` | `Optional[str]` | `None` | Base endpoint path, e.g. `"/user"` |
| `model` | `Optional[Type]` | `None` | ORM model class |
| `db_session` | `Optional[Callable]` | `None` | Database session factory function |
| `response_model` | `Optional[Type[BaseModel]]` | `None` | Pydantic schema for request/response bodies |
| `orm_adapter` | `Optional[BaseORMAdapter]` | `None` | ORM adapter; resolved from config when omitted |
| `**kwargs` | — | — | Forwarded to `fastapi.APIRouter` (e.g. `tags`, `prefix`, `dependencies`) |

### CRUD handlers

#### `list()`

```python
def list(
    self,
    limit: Optional[int] = 10,
    offset: Optional[int] = 0,
    search: Optional[str] = None,
    token: str = Depends(_noop_dependency),
) -> List[ResponseModelType]
```

List items with `limit`/`offset` pagination. Returns a list of `response_model` instances.

!!! warning "`search` parameter is reserved"

    The `search` parameter is accepted by `list()` and appears in the
    OpenAPI schema, but ORM adapters currently ignore it. Server-side
    search is planned for v1.4. Until then, override `list()` in a
    subclass to implement filtering — see
    [Pagination & Filtering](pagination-filtering.md).

#### `get_element()`

```python
def get_element(
    self,
    id: Union[int, str],
    token: str = Depends(_noop_dependency),
) -> ResponseModelType
```

Retrieve a single item by ID. Raises `404` if `id` is empty or `None`.

#### `create_element()`

```python
def create_element(
    self,
    item: ResponseModelType = Body(...),
    token: str = Depends(_noop_dependency),
) -> ResponseModelType
```

Create a new item from the request body.

#### `update_element()`

```python
def update_element(
    self,
    id: Union[int, str],
    item: ResponseModelType = Body(...),
    token: str = Depends(_noop_dependency),
    partial: bool = False,
) -> ResponseModelType
```

Update an existing item. `partial=True` (used by `PATCH`) only writes fields the client explicitly set, preserving correct PATCH semantics under Pydantic v2.

#### `delete_element()`

```python
def delete_element(
    self,
    id: Union[int, str],
    token: str = Depends(_noop_dependency),
) -> Dict[str, Union[bool, str]]
```

Delete an item by ID. Returns `{"status": True, "text": "successfully deleted"}` or `{"status": False, "text": "deletion failed"}`.

---

## `AsyncBaseViewset`

```python
from fastapi_viewsets import AsyncBaseViewset
```

Asynchronous CRUD viewset. Mirrors `BaseViewset` but every CRUD handler is `async`, backed by an async-capable ORM adapter (SQLAlchemy `AsyncSession` or Tortoise ORM).

### Constructor

Same parameters as `BaseViewset`, but `db_session` should be an async session factory (`Callable[[], AsyncSession]`).

### CRUD handlers

Identical signatures to `BaseViewset`, but `async def`:

- `async def list(...)`
- `async def get_element(...)`
- `async def create_element(...)`
- `async def update_element(...)`
- `async def delete_element(...)`

---

## `register()`

```python
def register(
    self,
    methods: Optional[List[str]] = None,
    oauth_protect: Optional[OAuth2PasswordBearer] = None,
    protected_methods: Optional[List[str]] = None,
) -> None
```

Register CRUD endpoints on the router.

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `methods` | `Optional[List[str]]` | `None` (all) | Logical methods to register |
| `oauth_protect` | `Optional[OAuth2PasswordBearer]` | `None` | OAuth2 dependency for protected operations |
| `protected_methods` | `Optional[List[str]]` | `None` | Subset of `methods` requiring the bearer token |

### Allowed methods

```python
ALLOWED_METHODS = ["LIST", "POST", "GET", "PUT", "PATCH", "DELETE"]
```

### Method-to-route mapping

| Logical method | HTTP method | Path | Handler | Response |
| --- | --- | --- | --- | --- |
| `LIST` | `GET` | `/` | `list` | `List[response_model]` |
| `GET` | `GET` | `/{id}` | `get_element` | `response_model` |
| `POST` | `POST` | `/` | `create_element` | `response_model` |
| `PUT` | `PUT` | `/{id}` | `update_element` (`partial=False`) | `response_model` |
| `PATCH` | `PATCH` | `/{id}` | `update_element` (`partial=True`) | `response_model` |
| `DELETE` | `DELETE` | `/{id}` | `delete_element` | `None` (raw dict) |

---

## `ORMFactory`

```python
from fastapi_viewsets.orm.factory import ORMFactory
```

Central entry point for adapter resolution.

### Methods

| Method | Returns | Description |
| --- | --- | --- |
| `get_default_adapter()` | `BaseORMAdapter` | Returns the cached singleton adapter for the current `ORM_TYPE` |
| `create_adapter(orm_type, config)` | `BaseORMAdapter` | Creates a new adapter instance from a dict config |
| `register_adapter(orm_type, adapter_class)` | `None` | Registers a custom adapter class (e.g. for a new ORM) |
| `get_adapter_from_env()` | `BaseORMAdapter` | Builds an adapter from environment variables (used internally by `get_default_adapter`) |
| `reset_default_adapter()` | `None` | Clears the cached singleton; the next `get_default_adapter()` call rebuilds from env. Useful in tests and hot-reload scenarios. |

---

## `BaseORMAdapter`

```python
from fastapi_viewsets.orm.base import BaseORMAdapter
```

Abstract base class for ORM adapters. All adapters (SQLAlchemy, Tortoise, Peewee) implement this interface.

### Abstract methods

| Method | Sync/Async | Description |
| --- | --- | --- |
| `get_session()` | Sync | Get a synchronous database session |
| `get_async_session()` | Sync | Get an async database session |
| `get_base()` | Sync | Get the base class for ORM models |
| `get_list_queryset(model, db_session, limit, offset, select_related, prefetch_related)` | Sync | Get a paginated list of model instances |
| `get_list_queryset_async(model, db_session, limit, offset, select_related, prefetch_related)` | Async | Async version of `get_list_queryset` |
| `get_element_by_id(model, db_session, id, select_related, prefetch_related)` | Sync | Get a single element by ID |
| `get_element_by_id_async(model, db_session, id, select_related, prefetch_related)` | Async | Async version of `get_element_by_id` |
| `create_element(model, db_session, data)` | Sync | Create a new element |
| `create_element_async(model, db_session, data)` | Async | Async version of `create_element` |
| `update_element(model, db_session, id, data, partial)` | Sync | Update an element (`partial=True` for PATCH) |
| `update_element_async(model, db_session, id, data, partial)` | Async | Async version of `update_element` |
| `delete_element(model, db_session, id)` | Sync | Delete an element by ID |
| `delete_element_async(model, db_session, id)` | Async | Async version of `delete_element` |
| `get_model_columns(model)` | Sync | Get column information for a model |

---

## `db_conf` module

```python
from fastapi_viewsets.db_conf import (
    ORM_TYPE,
    SQLALCHEMY_DATABASE_URL,
    get_orm_adapter,
    # Lazy SQLAlchemy globals:
    engine,
    Base,
    SessionLocal,
    db_session,
    get_session,
    async_engine,
    AsyncSessionLocal,
    get_async_session,
)
```

### Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `ORM_TYPE` | `sqlalchemy` | Active ORM: `sqlalchemy`, `tortoise`, or `peewee` |
| `DATABASE_URL` | `sqlite:///<cwd>/base.db` | Generic database URL (fallback) |
| `SQLALCHEMY_DATABASE_URL` | — | SQLAlchemy-specific URL |
| `SQLALCHEMY_ASYNC_DATABASE_URL` | Auto-derived | Explicit async URL (overrides auto-conversion) |
| `TORTOISE_DATABASE_URL` | — | Tortoise database URL |
| `TORTOISE_MODELS` | — | JSON list of model modules, e.g. `["app.models"]` |
| `TORTOISE_APP_LABEL` | `models` | Tortoise app label |
| `PEEWEE_DATABASE_URL` | — | Peewee database URL |

### Lazy resolution

SQLAlchemy globals (`engine`, `Base`, `get_session`, `get_async_session`, etc.) are resolved lazily on first access. Importing the package does not create engines unless they are needed, and works without async drivers installed.

---

## Serializer utilities

```python
from fastapi_viewsets.serializer_utils import get_select_related, get_prefetch_related
```

These helpers read eager-loading configuration from a Pydantic schema's inner `RelatedConfig` class. They are used internally by `get_list_queryset` and `get_element_by_id` (sync and async) when a `response_model` is provided.

| Function | Returns | Description |
| --- | --- | --- |
| `get_select_related(response_model)` | `List[str]` | Reads `RelatedConfig.select_related` (FK / many-to-one relations) |
| `get_prefetch_related(response_model)` | `List[str]` | Reads `RelatedConfig.prefetch_related` (collections / M2M relations) |

See [Eager Loading](eager-loading.md) for usage examples.

---

## Internal auth placeholder

The `token` parameter on every CRUD handler defaults to `Depends(_noop_dependency)`, where `_noop_dependency` is a private function that returns `None`. It is overridden when `oauth_protect` is passed to `register()`. The backward-compatible alias `butle` also points to this function.

You should not import `_noop_dependency` directly. If you override a handler and want to preserve the optional-auth behaviour, use `Depends(lambda: None)` or your own no-op dependency.

---

## Constants

```python
from fastapi_viewsets.constants import ALLOWED_METHODS, MAP_METHODS
```

### `ALLOWED_METHODS`

```python
ALLOWED_METHODS = ["LIST", "POST", "GET", "PUT", "PATCH", "DELETE"]
```

### `MAP_METHODS`

Maps logical method names to their route specifications:

```python
MAP_METHODS = {
    "GET":    {"method": "get_element",    "http_method": "GET",    "path": "/{id}", "is_list": False},
    "POST":   {"method": "create_element", "http_method": "POST",   "path": "",      "is_list": False},
    "PUT":    {"method": "update_element", "http_method": "PUT",    "path": "/{id}", "is_list": False},
    "PATCH":  {"method": "update_element", "http_method": "PATCH",  "path": "/{id}", "is_list": False},
    "DELETE": {"method": "delete_element", "http_method": "DELETE", "path": "/{id}", "is_list": False},
    "LIST":   {"method": "list",           "http_method": "GET",    "path": "",      "is_list": True},
}
```
