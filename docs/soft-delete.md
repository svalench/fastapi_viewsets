# Soft Delete & Restore

Soft deletion is optional and configured per viewset. The supported combinations
are SQLAlchemy with `BaseViewset` or `AsyncBaseViewset`, Tortoise with
`AsyncBaseViewset`, and Peewee with `BaseViewset`.

## Boolean marker

First add an `is_deleted` boolean column to the ORM model and migrate existing
rows to `False`. For example, with SQLAlchemy:

```python
from sqlalchemy import Boolean, Column

# Inside your SQLAlchemy model:
is_deleted = Column(Boolean, nullable=False, default=False, server_default="false")
```

The corresponding Tortoise field is `fields.BooleanField(default=False)`;
Peewee uses `BooleanField(default=False)`. Then configure the viewset:

```python
from fastapi.security import OAuth2PasswordBearer
from fastapi_viewsets import BaseViewset, SoftDeleteConfig

items = BaseViewset(
    endpoint="/items",
    model=Item,
    response_model=ItemSchema,
    db_session=get_session,
    soft_delete=SoftDeleteConfig(),
)
items.register(
    oauth_protect=OAuth2PasswordBearer(tokenUrl="/token"),
    protected_methods=["DELETE"],
)
app.include_router(items)
```

For async SQLAlchemy or Tortoise, use `AsyncBaseViewset` and the appropriate
adapter/session factory. `orm_adapter=...` can be passed as usual. Configuring one
viewset does not change other viewsets using the same model or adapter.

## Timestamp marker

Use a nullable datetime column when you need to retain the deletion time:

```python
policy = SoftDeleteConfig(field="deleted_at", mode="timestamp")
```

Pass `soft_delete=policy` to the viewset. An active row has `deleted_at = NULL`;
DELETE writes the current UTC datetime, and restore clears it to NULL. Prefer a
timezone-aware column when supported by your database. With SQLAlchemy use
`Column(DateTime(timezone=True), nullable=True)`, with Tortoise use
`fields.DatetimeField(null=True)`, and with Peewee use `DateTimeField(null=True)`.

Configuration rejects missing columns, primary keys, and mismatched marker types
when constructing the viewset. Timestamp columns must be nullable. The package
does not add columns or run migrations. Backfill boolean markers to False;
boolean NULL values are not considered active.

## HTTP behavior

| Operation | Behavior with soft deletion enabled |
| --- | --- |
| `GET /items` | Only active rows; filtering happens before limit/offset |
| `GET /items/{id}` | Deleted and missing records return 404 |
| `POST /items` | Always creates an active record |
| `PUT/PATCH /items/{id}` | Deleted records return 404; marker changes in bodies are ignored |
| `DELETE /items/{id}` | Marks an active record deleted and returns the existing success response |
| `POST /items/{id}/restore` | Restores a deleted record; active and missing records return 404 |

Restore returns `{"status": true, "text": "successfully restored"}`. Repeating
DELETE on a deleted record returns 404 and does not replace its deletion time.
Search, ordering, query filters, and eager loading continue to work. Query
parameters, including `include_deleted`, cannot remove the active-record filter.

## Route selection and permissions

`register()` automatically adds RESTORE when soft deletion is enabled and DELETE
is registered. Explicit `methods=["RESTORE"]` can expose only restoration; adding
RESTORE without a soft-delete configuration raises `ValueError`. Registering only
LIST/GET does not add a restore route. There is no built-in permanent-delete route
for a soft-delete viewset.

RESTORE inherits DELETE's protection when DELETE is listed in `protected_methods`.
It can also be protected explicitly with `protected_methods=["RESTORE"]`. With no
configured OAuth2 dependency, routes remain public, matching other CRUD methods.
`OAuth2PasswordBearer` extracts a token; application-specific token validation and
object permissions remain your responsibility, as described in
[Authentication](authentication.md).

## Constraints, relations and custom adapters

Soft-deleted rows still occupy unique values unless the application defines a
database-specific partial unique index. If restoring a record would violate a
constraint, the endpoint returns 409 and leaves its marker unchanged. Restoration
does not merge records or resolve those conflicts automatically.

The policy applies to the viewset's root records. It does not cascade to children,
change direct ORM queries, or filter records embedded through relationships.
Eager loading still uses the existing `RelatedConfig` behavior.

The default `soft_delete=None` retains physical DELETE and existing routes.
Third-party adapters need no changes for existing usage. An adapter wishing to
support the option must explicitly declare `supports_soft_delete = True`, support
the optional `soft_delete` keyword on its CRUD methods, and implement the relevant
`restore_element`/`restore_element_async` method. Optional base restore methods are
not abstract, so existing adapters remain instantiable.
