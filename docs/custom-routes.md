# Custom Routes & Permissions

## Adding custom routes

There is no `get_queryset` hook; scope queries by subclassing `BaseViewset` and overriding `list()`, `get_element()`, or related handlers. The class subclasses `APIRouter`, so you can attach extra endpoints with `add_api_route` **before** calling `register()` if the paths must take priority over `/{id}`:

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


# Instantiate with model, response_model, and db_session (see quickstart),
# then call register().
```

### Route ordering matters

Static routes (like `/items/stats`) must be registered **before** `register()` adds the `/{id}` route. Otherwise FastAPI may match `stats` against the `{id}` path parameter.

The internal `register()` method already sorts `LIST` before `GET` for this reason, but custom routes you add yourself need manual ordering.

## Permissions model

`fastapi-viewsets` uses a per-method OAuth2 approach rather than a full permissions framework:

- **Authentication** — `OAuth2PasswordBearer` on selected methods (see [Authentication](authentication.md))
- **Authorization** — implement in your override by inspecting the `token` or request user

Example with role-based access:

```python
from typing import Optional, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from fastapi_viewsets import AsyncBaseViewset

oauth2 = OAuth2PasswordBearer(tokenUrl="/token")


def _noop() -> None:
    """Placeholder dependency when OAuth2 is not active."""
    return None


class AdminOnlyDelete(AsyncBaseViewset):
    """Only admin users can DELETE; reads are public."""

    # NOTE: ``get_current_user`` is your own helper that decodes the JWT
    # and returns a user object with an ``is_admin`` flag.
    # Replace it with your actual authentication dependency.

    async def delete_element(
        self,
        id: Union[int, str],
        token: Optional[str] = Depends(oauth2),
    ) -> dict:
        # Validate the token and check role
        user = await get_current_user(token)  # your dependency/helper
        if not user.is_admin:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Admin access required",
            )
        return await super().delete_element(id, token=token)


# Register with DELETE protected:
viewset = AdminOnlyDelete(
    endpoint="/items",
    model=Item,
    response_model=ItemSchema,
    db_session=get_async_session,
)
viewset.register(
    methods=["LIST", "GET", "DELETE"],
    oauth_protect=oauth2,
    protected_methods=["DELETE"],
)
```

## The `APIRouter` connection

`BaseViewset` and `AsyncBaseViewset` both subclass `fastapi.APIRouter`. This means:

- `app.include_router(viewset)` works out of the box
- `add_api_route()`, `add_api_websocket_route()`, and all router methods are available
- Middleware and dependencies from the parent app apply to viewset routes
- You can nest viewsets in sub-routers with `APIRouter`'s `include_router`

## Next steps

- [Overriding Handlers](overrides.md) — subclassing patterns
- [Authentication](authentication.md) — OAuth2 setup details
- [API Reference](api-reference.md) — full method documentation
