# Release v1.5.2

Bugfix release for the CRUD write paths, route registration, and
packaging. All fixes are covered by regression tests
(`tests/test_write_path_regressions.py`).

## 🐞 Fixes

### Route registration

- **Body-schema leak between viewsets (critical).** `register()` used to
  mutate `__annotations__` of the shared class-level CRUD functions, so
  in any process with two or more viewsets every `POST`/`PUT`/`PATCH`
  endpoint validated against the *last registered* viewset's schema.
  Handlers are now cloned per instance before the body annotation is
  patched.
- **PATCH is truly partial.** The PATCH body is validated against an
  auto-generated all-optional variant of the `response_model`
  (`<Schema>Patch`). Previously a partial PATCH body failed validation
  with `422` whenever the schema had required fields.
- **PATCH honors explicit `null`.** Explicitly sent JSON `null` now
  clears a nullable column instead of being silently dropped.
- **Pagination validated.** Negative `limit`/`offset` are rejected with
  `422`; `limit` is capped at 10000. Defaults (`limit=10`, `offset=0`)
  are documented.
- **Filters in OpenAPI.** Whitelisted `ListConfig.filters` fields and
  their `__op` variants (`__gte`, `__in`, …) are advertised in the
  generated OpenAPI schema and Swagger UI.

### ORM adapters (SQLAlchemy sync/async, Tortoise, Peewee)

- **PUT no longer nulls columns absent from the schema.** Only fields
  explicitly present in the payload are written; the primary key is
  never overwritten. Previously `PUT` set every non-schema column to
  `NULL` (data loss).
- **Create strips an explicit `NULL` primary key.** Schemas with
  `id: Optional[int] = None` no longer break `POST` on Tortoise
  (`id is non nullable field, but null was passed`) and no longer send
  `NULL` for the PK on backends like PostgreSQL.
- **Integrity violations return `409 Conflict`** with a sanitized
  message (`"Integrity error: a database constraint was violated"`).
  Raw SQL, parameters and driver internals are no longer exposed in
  response bodies; generic adapter errors likewise use static messages.

### Packaging

- Base install is now truly ORM-agnostic: `SQLAlchemy` and `uvicorn`
  were removed from core dependencies. The package imports cleanly
  without SQLAlchemy installed.
- `fastapi-viewsets[sqlalchemy]` now installs `SQLAlchemy[asyncio]`,
  which includes `greenlet` — async sessions work out of the box.

## ⚠️ Behavior changes to be aware of

- Integrity violations: `400` → `409` (message no longer contains raw SQL).
- PATCH with explicit `null` writes `NULL` (previously ignored).
- PUT no longer clears fields/columns missing from the payload.
- `pip install fastapi-viewsets` no longer pulls SQLAlchemy/uvicorn —
  use `fastapi-viewsets[sqlalchemy]` and install `uvicorn` to run apps.
