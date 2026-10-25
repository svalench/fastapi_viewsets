# Nested Resources

`NestedConfig` binds a child resource to a parent from the URL. It works with
SQLAlchemy (sync/async), Tortoise (async), and Peewee (sync). Existing viewsets
retain their behavior when `nested` is omitted.

```python
from fastapi_viewsets import BaseViewset, NestedConfig

comments = BaseViewset(
    endpoint="/posts/{post_id}/comments",
    model=Comment,
    response_model=CommentSchema,
    db_session=get_session,
    nested=NestedConfig(parent_model=Post, foreign_key="post_id"),
)
comments.register()
app.include_router(comments)
```

Each generated route resolves the parent once and restricts the child operation
to that parent. Missing parents and children belonging to a different parent
return 404. Search, filters, ordering, and pagination operate within this scope.

## Full example

This example uses SQLAlchemy with a real foreign key. A comment can be created
with just `{"text": "Hello"}`; the URL supplies `post_id`.

Install the SQLAlchemy extra with `pip install "fastapi-viewsets[sqlalchemy]"`.

```python
from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, ForeignKey, Integer, String

from fastapi_viewsets import BaseViewset, NestedConfig
from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter

adapter = SQLAlchemyAdapter(database_url="sqlite:///nested.db")
Base = adapter.get_base()


class Post(Base):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)


class Comment(Base):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    text = Column(String, nullable=False)


class PostSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    title: str


class CommentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    post_id: int
    text: str


Base.metadata.create_all(adapter.engine)  # Use migrations in production.
app = FastAPI()

posts = BaseViewset(
    endpoint="/posts", model=Post, response_model=PostSchema,
    db_session=adapter.get_session, orm_adapter=adapter,
)
posts.register()

comments = BaseViewset(
    endpoint="/posts/{post_id}/comments", model=Comment,
    response_model=CommentSchema,
    db_session=adapter.get_session, orm_adapter=adapter,
    nested=NestedConfig(parent_model=Post, foreign_key="post_id"),
)
comments.register()
app.include_router(posts)
app.include_router(comments)
```

For async SQLAlchemy or Tortoise use `AsyncBaseViewset` with the appropriate
adapter/session factory. Parent and child use the same adapter and session
factory. The library does not add database columns, constraints, or migrations.

## Configuration

| Setting | Meaning |
| --- | --- |
| `parent_model` | Parent ORM class; its single primary key must be exposed as `id` |
| `foreign_key` | Child ORM field or supported raw FK accessor |
| `path_param` | Parent path parameter name; defaults to `foreign_key` |
| `parent_soft_delete` | Optional `SoftDeleteConfig` for filtering the parent lookup |

SQLAlchemy uses the mapped scalar attribute, such as `post_id`, even when the
database column has a different name. Tortoise supports `post` and `post_id` for a
`ForeignKeyField`. Peewee supports the `ForeignKeyField` name and its raw-ID
accessor (`post_id` by default; `object_id_name` can customize it).

The configuration rejects missing fields, primary-key fields, declared
relations to another parent model/key, and conflicting CRUD parameter names.
Parent IDs support integer, string, and UUID model types. Invalid integer/UUID
path values return 422. Composite parent keys and relations targeting fields
other than the parent's `id` are not supported.

You can put the parent path in an outer router:

```python
comments = BaseViewset(
    endpoint="/comments", model=Comment, response_model=CommentSchema,
    db_session=get_session,
    nested=NestedConfig(parent_model=Post, foreign_key="post_id", path_param="post_pk"),
)
comments.register()
parent_router = APIRouter(prefix="/posts/{post_pk}")
parent_router.include_router(comments)
app.include_router(parent_router)
```

The final mounted route must contain the configured path parameter. A request
without it fails validation; the viewset never falls back to an unscoped query.

## Request and response behavior

| Operation | Behavior |
| --- | --- |
| LIST | Verifies the parent and filters children before pagination |
| GET | Looks up the child by both its ID and parent |
| POST | Binds the foreign key to the resolved parent's ID |
| PUT/PATCH | Restricts lookup/update to the parent and prevents reparenting |
| DELETE | Deletes only a child within the parent scope |
| RESTORE | Restores only a deleted child within the parent scope, when soft deletion is enabled |

URL binding takes precedence over FK values in JSON bodies. The server supplies
the bound value before validating the body and enforces it again in the ORM
operation. Ordinary body constraints and validators are preserved. The original
response schema is not modified, and the parent field is optional in the generated
request schema. Schemas may omit the FK entirely. Flat string aliases and
`AliasChoices` are supported; deep `AliasPath` bindings are rejected during
registration. PATCH retains the existing partial-model validation rules.

Query parameters cannot override the parent scope. Scoped physical deletion uses
normal ORM instance deletion, preserving its lifecycle and cascade behavior.

## Parent context and permissions

Inside a generated handler, `self.get_parent()` returns the resolved parent
object. It is also available as `request.state.viewset_parent`. Context is local
to each request and is propagated to synchronous handlers running in worker
threads. The router itself never stores the current parent object.

Override `resolve_parent(request)` to add application-specific parent access
checks. The async viewset uses an async hook:

```python
from fastapi import HTTPException, Request
from fastapi_viewsets import AsyncBaseViewset


class AuthorizedComments(AsyncBaseViewset):
    async def resolve_parent(self, request: Request):
        parent = await super().resolve_parent(request)
        # Your authentication dependency supplies request.state.user.
        if not request.state.user.can_access(parent):
            raise HTTPException(status_code=403, detail="Forbidden parent")
        return parent
```

The default resolver raises 404 for missing parents. In a synchronous viewset,
use `def resolve_parent(...)` and call `super().resolve_parent(request)`.
Authentication configured through `register()` runs before parent lookup for
protected operations. FK scoping does not automatically implement ownership or
tenant permissions; use your normal authentication dependency and this hook.

For custom routes added outside `register()`, opt into the context dependency
explicitly and configure their authentication as usual:

```python
from fastapi import Depends, Request


@app.get("/posts/{post_id}/summary", response_model=PostSchema,
         dependencies=[Depends(comments.parent_context)])
def parent_summary(post_id: int, request: Request):
    return request.state.viewset_parent
```

`get_parent()` and nested CRUD methods require the current viewset's
`parent_context` dependency. Direct calls without that request context raise a
clear error instead of querying all children. One configured parent is supported
per viewset; for additional ancestor URL parameters, validate their relationship
in `resolve_parent()`.

## Combining with soft deletion

```python
policy = SoftDeleteConfig()
comments = BaseViewset(
    endpoint="/posts/{post_id}/comments", model=Comment,
    response_model=CommentSchema, db_session=get_session,
    soft_delete=policy,
    nested=NestedConfig(parent_model=Post, foreign_key="post_id", parent_soft_delete=policy),
)
comments.register()
```

Both models must have the configured marker column. Child and parent policies
are independent: configure `parent_soft_delete` explicitly; the library does not
infer it from a separate parent router. A deleted parent blocks every nested
operation, including child restoration. Restore the parent before restoring a
child through `POST /posts/{post_id}/comments/{id}/restore`.

Soft deletion does not cascade marker changes to children. See
[Soft Delete & Restore](soft-delete.md) for restoration permissions and conflicts.

## Custom ORM adapters

Existing adapters need no changes while `nested=None`. Supporting nesting is
explicit: set `supports_nested = True`, accept and enforce the optional `scope`
keyword in CRUD and supported restore methods, and normalize FK field aliases
through `get_nested_field(model, field)`. Parent lookup uses the existing
`get_element_by_id` or `get_element_by_id_async` method. The base class supplies
optional hooks for parent ID types and declared-relation validation, without
adding abstract methods. `scope` contains trusted server-side equality predicates;
it must not be replaced by client query filters or mutable fields in request bodies.
