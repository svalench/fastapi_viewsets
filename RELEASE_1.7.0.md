# fastapi-viewsets 1.7.0

Version 1.7.0 adds opt-in soft deletion/restoration and nested resources across
SQLAlchemy (sync/async), Tortoise ORM (async), and Peewee (sync). Existing viewsets
keep their behavior until the new options are enabled.

## Soft delete and restore

- Configure `soft_delete=SoftDeleteConfig()` for an `is_deleted` boolean marker,
  or `SoftDeleteConfig(field="deleted_at", mode="timestamp")` for a nullable
  datetime marker.
- DELETE marks the record deleted. LIST/GET hide deleted rows, and ordinary
  PUT/PATCH/DELETE requests on them return 404. Filtering happens before pagination.
- `POST /{id}/restore` restores a deleted row and inherits DELETE's configured
  OAuth2 protection. Active/missing IDs return 404; constraint conflicts return 409.
- Client bodies cannot change the managed marker through POST/PUT/PATCH, and query
  filters cannot bypass the active-row restriction.

## Nested resources

Configure `nested=NestedConfig(parent_model=Post, foreign_key="post_id")` on
`/posts/{post_id}/comments` to automatically resolve the parent and constrain
child CRUD and restoration to it.

- Missing parents and children belonging to another parent return 404.
- The URL supplies the foreign key before body validation; JSON/query values
  cannot reparent records or replace the parent scope.
- Read the resolved object through `get_parent()` or `request.state.viewset_parent`.
  Override `resolve_parent(request)` to enforce application-specific permissions.
- Request-local context supports concurrent sync/async handlers.
- Integer/string/UUID parent IDs, custom path parameter names, external router
  prefixes, mapped database column names, and flat Pydantic aliases are supported.
- Optional parent soft-delete filtering also protects nested child restoration.

## Compatibility and fixes

- Both options default to `None`; existing routes, physical deletion, and legacy
  custom adapters continue to work. Normal ORM deletion cascades are preserved.
- Applications must migrate/backfill their own deletion-marker columns before
  enabling soft deletion. The package does not change database schemas or cascade
  deletion markers to related records.
- A nested parent must expose a single primary key as `id`. Ownership and
  additional ancestor/tenant permissions remain application-specific.
- Fix Tortoise required-field validation to exclude virtual/backward relations.
- Preserve wrapped-handler annotation namespaces for OAuth2 registration with
  FastAPI 0.110 and newer versions.

## Validation

496 tests passed on each of two SQLite-backed environments:

- Python 3.13, FastAPI 0.162.0, Pydantic 2.14.1, current ORM dependencies;
  branch-aware coverage: 90.13%.
- Python 3.11, FastAPI 0.110.0, Pydantic 2.5.0, SQLAlchemy 2.0.0,
  Tortoise ORM 0.20.0, Peewee 3.17.0; coverage: 90.41%.

The documented nested example is exercised against the installed wheel.
Wheel and source distributions passed `twine check --strict`.

## Upgrade and guides

```bash
pip install --upgrade "fastapi-viewsets[sqlalchemy]==1.7.0"
```

[Soft Delete & Restore](https://github.com/svalench/fastapi_viewsets/blob/v1.7.0/docs/soft-delete.md)
· [Nested Resources](https://github.com/svalench/fastapi_viewsets/blob/v1.7.0/docs/nested-resources.md)
· [Full changelog](https://github.com/svalench/fastapi_viewsets/compare/v1.5.3...v1.7.0)
