# Changelog

## v1.3.0

- **Declarative eager loading** via `RelatedConfig` inside Pydantic schemas.
    Add `select_related = [...]` and/or `prefetch_related = [...]` to a schema's inner `RelatedConfig` class, and `BaseViewset` / `AsyncBaseViewset` automatically applies `joinedload` / `selectinload` (SQLAlchemy) or `prefetch_related` (Tortoise) on `LIST` and `GET` endpoints. This eliminates N+1 queries without duplicating configuration between schemas and viewsets.
- All adapter methods (`get_list_queryset`, `get_element_by_id`, and their async counterparts) accept optional `select_related` and `prefetch_related` arguments for explicit overrides.
- Full backward compatibility: new parameters default to `None`; existing code works unchanged.

## v1.2.2

- **Documentation overhaul**: added async + Pydantic v2 quickstart and override examples to README.

## v1.2.1

- **Hotfix: `SQLAlchemyAdapter` no longer crashes at construction** when the async DB-API driver (`aiosqlite` / `asyncpg` / `aiomysql`) is missing. Sync-only setups keep working out of the box; `get_async_session()` raises a helpful `RuntimeError` lazily if you try to use async without the driver.

## v1.2.0

- Pydantic v2 first: CRUD handlers use `model_dump(exclude_unset=...)`, fixing PATCH semantics that previously overwrote unset fields with defaults.
- Lazy `db_conf`: importing the package no longer creates SQLAlchemy engines unless they are needed, and works without async drivers installed.
- Single source of truth for sync-to-async URL conversion and the default adapter singleton.
- Internal `register()` deduplicated between sync and async viewsets via a shared mixin.
- PEP 621 `pyproject.toml`, `python_requires>=3.9`, FastAPI `>=0.110`, ruff/black/mypy preconfigured.

## v1.1.0

- Multi-ORM support via adapters (SQLAlchemy default, optional Tortoise and Peewee).
- `ORMFactory` and environment-driven `ORM_TYPE` configuration.

## Links

- [GitHub releases](https://github.com/svalench/fastapi_viewsets/releases)
- [PyPI](https://pypi.org/project/fastapi-viewsets/)
- [Release notes (v1.3.0)](https://github.com/svalench/fastapi_viewsets/blob/master/RELEASE_1.3.0.md)
- [Release notes (v1.2.0)](https://github.com/svalench/fastapi_viewsets/blob/master/RELEASE_1.2.0.md)
- [Release notes (v1.1.0)](https://github.com/svalench/fastapi_viewsets/blob/master/RELEASE_1.1.0.md)
