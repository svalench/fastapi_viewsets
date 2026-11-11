# Object-level permissions (v1.8.0)

`fastapi-viewsets` separates **authentication** (is the caller logged in?) from **authorization** (may this caller touch this row?).

- `oauth_protect` / a custom `auth_dependency` should populate `request.state.user`.
- Optional `permission_classes` on a viewset enforce action and object checks, and merge row-level filters into the existing ORM `scope` (the same mechanism used by nested resources and soft-delete).

Viewsets **without** `permission_classes` behave exactly as before.

## Built-in classes

| Class | Purpose |
| --- | --- | --- |
| `IsAuthenticated` | Requires `request.state.user` |
| `IsOwner` | Restricts LIST/GET/updates/deletes to rows owned by the user; staff/admin (`is_staff`, `is_admin`, or `staff`) bypass the SQL filter |
| `IsAdminUser` / `IsAdmin` | Admin-only viewsets |

Each class implements:

- `has_permission(request, view, action)` — gate before queries run (`403` when false)
- `has_object_permission(request, view, action, obj)` — gate after a row is loaded
- `get_scope(request, view)` — extra equality filters merged into ORM queries

Custom classes can override `filter_queryset()` later for OR conditions or joins.

## 404 vs 403

- Missing or invalid authentication for a protected action → **`403 Forbidden`**
- Authenticated user requesting another user's id → **`404 Not Found`** (scope hides foreign rows; no existence leak)
- Authenticated user blocked by an explicit object rule → **`403 Forbidden`**

## Owner field

There is **no hidden default** such as `owner_id`. Choose one of:

1. `owner_field = "user_id"` on the viewset
2. `IsOwner(field="user_id")` in `permission_classes`
3. **Auto-detect** when the model has **exactly one** foreign key to the user model configured via `init_permissions(user_model=User)`

Auto-detect fails at viewset construction when there are zero user FKs, a bare integer column without FK, or two or more user relations — set `owner_field` explicitly.

On `POST`/`PUT`/`PATCH`, the owner column is set server-side from the current user; client-supplied owner ids in the body are stripped (same idea as nested parent binding).

## Full example

```python
from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from typing import Optional

from fastapi_viewsets import (
    BaseViewset,
    IsAuthenticated,
    IsOwner,
    init_permissions,
)
from fastapi_viewsets.db_conf import Base, engine, get_session

app = FastAPI()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True)
    is_staff = Column(Boolean, default=False)


class Note(Base):
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True)
    text = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)


class NoteSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    text: str
    user_id: Optional[int] = None


init_permissions(user_model=User)
Base.metadata.create_all(bind=engine)


def current_user(request: Request):
    # Load the user from your JWT/session here and assign:
    # request.state.user = user
    return request.state.user


class NotesViewset(BaseViewset):
    permission_classes = [IsAuthenticated, IsOwner]


notes = NotesViewset(
    endpoint="/notes",
    model=Note,
    response_model=NoteSchema,
    db_session=get_session,
)
notes.register(
    methods=["LIST", "GET", "POST", "PATCH", "DELETE"],
    auth_dependency=current_user,
)
app.include_router(notes)
```

`oauth_protect` can still wrap selected methods; ensure the same dependency (or middleware) sets `request.state.user`.

## See also

- [Authentication](authentication.md) — bearer tokens vs authorization
- [Nested Resources](nested-resources.md) — parent scoping combines with permission `scope`
- [Soft Delete & Restore](soft-delete.md)
