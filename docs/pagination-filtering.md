# Pagination, Filtering & Ordering

## Pagination

`BaseViewset.list` (and `AsyncBaseViewset.list`) map `limit` and `offset` to query parameters on the LIST route.

```
GET /items?limit=10&offset=20
```

| Parameter | Type | Default | Description |
| --- | --- | --- | --- |
| `limit` | `Optional[int]` | `10` | Maximum number of items to return |
| `offset` | `Optional[int]` | `0` | Number of items to skip |
| `search` | `Optional[str]` | `None` | Search query (reserved — see below) |

Example:

```text
# Default: GET /items → 10 items, offset 0
GET /items

# Custom page: GET /items?limit=50&offset=100 → items 101-150
GET /items?limit=50&offset=100
```

No additional configuration needed — pagination is built into the default `list()` handler.

## Filtering

!!! warning "`search` is reserved but not yet wired"

    The `search` parameter is accepted by `list()` but ORM adapters currently ignore it. Server-side search is on the [Roadmap](#roadmap) for v1.4.

Until then, subclass `BaseViewset` or `AsyncBaseViewset` and override `list()` with your own filtering logic:

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
        """Custom LIST with case-insensitive search."""
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

## Ordering

There is no built-in `order_by` helper yet. Override `list()` with an ordered query:

```python
from sqlalchemy import select


class OrderedItems(AsyncBaseViewset):
    async def list(
        self,
        limit: int = 10,
        offset: int = 0,
        token: Optional[str] = Depends(lambda: None),
    ):
        session = self.db_session()
        try:
            stmt = select(self.model).order_by(self.model.created_at.desc())
            stmt = stmt.offset(offset).limit(limit)
            rows = (await session.execute(stmt)).scalars().all()
            return [self.response_model.model_validate(row) for row in rows]
        finally:
            await session.close()
```

## Roadmap

| Item | Target | Status |
| --- | --- | --- |
| Wire `search` on LIST to real database queries | v1.4 | Planned |
| Declarative ordering (`order_by`) on LIST endpoints | v1.4 | Planned |
| Advanced filters (`__gt`, `__lt`, `__in`) via query params | v1.5 | Planned |
| Transaction helpers (`begin` / `atomic`) across adapters | v1.4 | Planned |

## Next steps

- [Overriding Handlers](overrides.md) — complete override example
- [API Reference](api-reference.md) — `list()` signature and parameters
