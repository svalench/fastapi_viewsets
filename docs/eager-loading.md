# Eager Loading (`select_related` / `prefetch_related`)

If your Pydantic schema includes nested models (e.g. `author: UserSchema`), SQLAlchemy will normally emit extra queries for every row — the classic **N+1 problem**. You can fix this declaratively by adding an inner `RelatedConfig` class to the schema.

## How it works

```python
from pydantic import BaseModel, ConfigDict


class AuthorSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str


class PostSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    author: AuthorSchema          # nested model → signals the need for a join

    class RelatedConfig:
        select_related = ["author"]   # FK / many-to-one  → one JOIN query
        prefetch_related = ["tags"]   # collections / M2M → separate SELECT IN
```

When `PostSchema` is passed as `response_model` to a viewset, `LIST` and `GET` automatically apply the correct eager-loading strategy:

```python
posts = AsyncBaseViewset(
    endpoint="/posts",
    model=Post,
    response_model=PostSchema,
    db_session=get_async_session,
)
```

No additional configuration on the viewset itself — the schema drives the behavior.

## ORM-specific behavior

| ORM | `select_related` | `prefetch_related` |
| --- | --- | --- |
| SQLAlchemy | `joinedload` (single query, FK side) | `selectinload` (two queries, collection side, no Cartesian product) |
| Tortoise ORM | Native `prefetch_related()` for both | Native `prefetch_related()` |
| Peewee | `.join()` for `select_related` | Not supported |

## When to use which

- **`select_related`** — for ForeignKey / many-to-one relationships. Uses a SQL `JOIN`, so everything comes back in one query. Best for single-object relations (e.g. `Post.author`).

- **`prefetch_related`** — for collections / many-to-many. Runs a separate `SELECT ... WHERE id IN (...)` query to avoid the Cartesian product. Best for list relations (e.g. `Post.tags`, `Post.comments`).

## Explicit overrides

You can also override the config per-call when using the low-level utilities directly:

```python
from fastapi_viewsets.async_utils import get_list_queryset

posts = await get_list_queryset(
    Post,
    db_session=get_async_session,
    response_model=PostSchema,
    select_related=["author"],
    prefetch_related=["tags", "comments"],
)
```

The adapter methods `get_list_queryset`, `get_element_by_id`, and their async counterparts all accept optional `select_related` and `prefetch_related` arguments for explicit overrides.

## Backward compatibility

!!! info "All new parameters default to `None`"

    Existing code and tests continue to work unchanged. If your schema doesn't have a `RelatedConfig` class, no eager loading is applied — identical to previous behavior.
