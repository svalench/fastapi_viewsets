# v1.6.0 — Soft Delete & Restore

Development milestone; this functionality is first published in v1.7.0.
See [the 1.7.0 release notes](RELEASE_1.7.0.md) for the combined release.

Soft deletion is opt-in per viewset, with support for SQLAlchemy sync/async,
Tortoise async, and Peewee sync. Import `SoftDeleteConfig` from `fastapi_viewsets`
and pass `soft_delete=SoftDeleteConfig()` to a viewset to use an `is_deleted`
boolean column. Use `SoftDeleteConfig(field="deleted_at", mode="timestamp")`
for a nullable datetime marker instead.

- DELETE changes the marker without removing the record or cascading deletion.
- LIST filters active records in the database before pagination; GET hides deleted
  records. PUT/PATCH and repeat DELETE return 404 for deleted records.
- POST to `/{id}/restore` restores deleted records; active and missing IDs return
  404. The route inherits DELETE's configured OAuth2 dependency.
- New records start active. Client bodies cannot change the managed marker through
  POST/PUT/PATCH, and query filters cannot bypass the active-record restriction.
- Database constraint violations during restore return 409 without SQL details.
- Preserve wrapped handler annotation namespaces for OAuth2 registration on
  FastAPI 0.110 as well as current FastAPI versions.

The application must migrate/backfill its own model column before enabling the
feature. Existing viewsets and third-party adapters remain unchanged when it is
disabled. Related objects, direct ORM queries, and other viewsets do not inherit
the policy. See [the guide](docs/soft-delete.md) for configuration and limitations.
