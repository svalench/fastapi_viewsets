# Overriding Handlers (Custom LIST and POST)

Every CRUD handler is a regular method, so subclassing the viewset is the canonical way to add filtering, ordering, validation, conflict handling, and more.

## Available handlers

| Handler | Logical method | HTTP | Path | Default behavior |
| --- | --- | --- | --- | --- |
| `list()` | `LIST` | `GET` | `/` | Paginated list with `limit` / `offset` |
| `get_element()` | `GET` | `GET` | `/{id}` | Retrieve by ID |
| `create_element()` | `POST` | `POST` | `/` | Create from request body |
| `update_element()` | `PUT` / `PATCH` | `PUT` / `PATCH` | `/{id}` | Full or partial update |
| `delete_element()` | `DELETE` | `DELETE` | `/{id}` | Delete by ID |

## Complete example: search + ordering + conflict handling

This example subclasses `AsyncBaseViewset` and overrides both `list` (case-insensitive search + simple ordering) and `create_element` (input normalization + mapping `IntegrityError` to 409).

```python
from typing import List, Optional

from fastapi import Body, HTTPException, status
from fastapi import Depends
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
        token: Optional[str] = Depends(lambda: None),
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
        token: Optional[str] = Depends(lambda: None),
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

## Key points when overriding

### Keep method names and the `item` body parameter

`register()` introspects `list`, `get_element`, `create_element`, `update_element`, `delete_element`. It also rewrites the `item.__annotation__` to `response_model` so the OpenAPI body schema stays consistent — use the same schema for request and response, or pre-validate inside the handler.

### Adding new query parameters is fine

`search`, `order_by`, filters, etc. — FastAPI picks them up automatically from the function signature.

### Manage your own session lifecycle

In overrides, manage sessions with `try/finally` + `await session.close()`, or use a FastAPI dependency with `yield`.

### Sync viewsets

For sync apps, the same pattern applies to `BaseViewset` — just drop the `async`/`await` and use `Session` instead of `AsyncSession`.

## What `register()` does internally

When you call `register()`:

1. **Sorts methods** — `LIST` is registered before `GET` so FastAPI doesn't match the collection path against `/{id}`.
2. **Patches annotations** — if the handler has an `item` parameter and `response_model` is set, the annotation is rewritten to your schema for OpenAPI consistency.
3. **Handles PUT vs PATCH** — both map to `update_element`, but `PATCH` passes `partial=True` (using `model_dump(exclude_unset=True)`).
4. **Applies OAuth2** — if `protected_methods` includes a method and `oauth_protect` is provided, the token dependency is wired via `functools.partial`.
5. **Adds routes** — `add_api_route()` is called with the computed endpoint path, response model, tags, and HTTP method.

## Next steps

- [Authentication](authentication.md) — OAuth2 on selected operations
- [Custom Routes](custom-routes.md) — adding endpoints alongside CRUD
- [API Reference](api-reference.md) — full class and method documentation
