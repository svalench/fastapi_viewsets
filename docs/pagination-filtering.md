# Pagination, Search, Ordering & Filtering

## Pagination

`BaseViewset.list` (and `AsyncBaseViewset.list`) map `limit` and `offset` to query parameters on the LIST route.

```
GET /items?limit=10&offset=20
```

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `limit` | `Optional[int]` | `10` | Maximum number of items to return |
| `offset` | `Optional[int]` | `0` | Number of items to skip |

No additional configuration needed — pagination is built into the default `list()` handler.

## Search, ordering and filters via `ListConfig`

Since v1.5.0 the LIST endpoint supports server-side search, declarative
ordering and whitelisted filters. Declare an inner `ListConfig` class on
your Pydantic response schema:

```python
from pydantic import BaseModel

class ItemSchema(BaseModel):
    id: int
    name: str
    status: str
    price: float

    class ListConfig:
        search_fields = ["name"]          # ?search=foo → case-insensitive substring
        ordering_fields = ["name", "price", "id"]  # ?ordering= allowed fields
        ordering = ["-id"]                # default ordering (newest first)
        filters = ["status", "price"]      # ?<field>=... allowed fields
```

That is all — the default `list()` handler picks the configuration up
automatically.

### Search

`GET /items?search=foo` performs a case-insensitive substring match,
OR-ed across every field in `search_fields`.

### Ordering

`GET /items?ordering=-price,name` orders by `price` descending, then
`name` ascending. A leading `-` means descending.

* The field must be listed in `ordering_fields`, otherwise the endpoint
  returns `400 Bad Request`.
* When the `ordering` parameter is omitted, the declarative default
  (`ListConfig.ordering`) applies.
* When `ordering_fields` is not declared, ordering via the query
  parameter is disabled (the parameter is ignored).

### Filters

Any field listed in `filters` can be filtered with an exact-match query
parameter, and supports operator suffixes:

| Example | Meaning |
| --- | --- |
| `?status=active` | `status == "active"` |
| `?status__ne=active` | `status != "active"` |
| `?price__gt=100` | `price > 100` |
| `?price__gte=100` | `price >= 100` |
| `?price__lt=100` | `price < 100` |
| `?price__lte=100` | `price <= 100` |
| `?name__contains=pro` | case-insensitive substring |
| `?status__in=active,pending` | `status IN (...)` |

* Fields not listed in `filters` are ignored — arbitrary fields never
  reach the ORM.
* Values are automatically coerced to `int` / `float` / `bool` when
  they parse.
* Everything composes: `?search=pro&status=active&ordering=-price&limit=5`.

All built-in adapters (SQLAlchemy sync/async, Tortoise ORM, Peewee)
implement search, ordering and filters. The utility layer
(`fastapi_viewsets.utils.get_list_queryset` /
`fastapi_viewsets.async_utils.get_list_queryset`) also accepts
`search`, `search_fields`, `ordering` and `filters` keyword arguments
for programmatic use.

### Backward compatibility

Without a `ListConfig` on the response schema, the LIST endpoint
behaves exactly as before: `?search=` is ignored (no fields to search),
`?ordering=` is ignored, and unknown query parameters are dropped.

## Custom filtering beyond the whitelist

For anything the declarative config does not cover, subclass
`BaseViewset` or `AsyncBaseViewset` and override `list()`:

```python
from typing import List, Optional

from fastapi import Depends
from sqlalchemy import select

from fastapi_viewsets import AsyncBaseViewset


class ItemsWithSearch(AsyncBaseViewset):
    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
        search: Optional[str] = None,
        token: Optional[str] = Depends(lambda: None),
    ) -> list:
        """Custom LIST with search beyond the whitelist."""
        session = self.db_session()
        try:
            stmt = select(self.model)
            if search:
                stmt = stmt.where(self.model.name.ilike(f"%{search}%"))
            stmt = stmt.offset(offset).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [self.response_model.model_validate(row) for row in rows]
        finally:
            await session.close()
```

See [Overriding Handlers](overrides.md) for the full example with search + ordering + conflict handling.

## Roadmap

| Item | Target | Status |
| --- | --- | --- |
| Server-side `search` on LIST | v1.5.0 | Released |
| Declarative ordering on LIST | v1.5.0 | Released |
| Advanced filters (`__gt`, `__lt`, `__in`, ...) via query params | v1.5.0 | Released |
| Date-range filters (`__range`) and null checks (`__isnull`) | future | Planned |
| Transaction helpers (`begin` / `atomic`) across adapters | future | Planned |

## Next steps

- [Overriding Handlers](overrides.md) — complete override example
- [API Reference](api-reference.md) — `list()` signature and parameters
