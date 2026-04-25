# Release 1.2.0 — Pydantic v2 + async/internal cleanup

This release modernizes the package for Pydantic v2 and removes
several long-standing rough edges around async support, configuration
loading and code duplication. There are no breaking changes for
applications that already pass Pydantic v2 schemas.

## Highlights

### Pydantic v2 first

- CRUD handlers now serialize request bodies via
  `model_dump(exclude_unset=...)` instead of the legacy `dict(item)`
  call.
- **PATCH semantics fixed**: with Pydantic v2, `model_dump(exclude_unset=True)`
  only returns fields the client actually sent. `BaseViewset.update_element`
  and `AsyncBaseViewset.update_element` use this for `partial=True`, so
  unset fields are no longer accidentally overwritten with defaults.
- New compatibility helper `fastapi_viewsets._compat.model_to_dict`
  transparently supports both Pydantic v1 (`.dict`) and v2 (`.model_dump`)
  models.
- Test suite migrated to `model_config = ConfigDict(from_attributes=True)`.
- `pydantic>=2.5,<3` is now a hard runtime dependency.

### Async/configuration cleanup

- `db_conf.py` resolves SQLAlchemy globals **lazily** via module-level
  `__getattr__`. Importing `fastapi_viewsets` no longer creates engines
  or imports SQLAlchemy when another ORM is selected, and no longer
  fails when an async driver such as `aiosqlite` is missing.
- The sync→async URL conversion (`sqlite:///` → `sqlite+aiosqlite:///`,
  etc.) lives in a single helper, `to_async_database_url`. Previously it
  was duplicated across `db_conf`, `factory` and the SQLAlchemy adapter.
- Removed the duplicate `_default_adapter` singleton from `db_conf`;
  `ORMFactory.get_default_adapter()` is now the only source of truth.
  `ORMFactory.reset_default_adapter()` was added for tests and hot
  reloads.

### Internal refactor

- `BaseViewset.register` and `AsyncBaseViewset.register` were two
  near-identical 90-line methods. They are now a single
  `_RegisterMixin.register` shared by both classes.
- Replaced bare `except: pass` blocks around annotation patching with a
  narrow `(AttributeError, TypeError)` guard.
- Renamed the no-op auth dependency from `butle` to `_noop_dependency`;
  `butle` is kept as a backward-compatible alias.
- Trimmed unused imports (`os`, duplicate `Any`).

### Packaging

- Added a PEP 621 `pyproject.toml` (with `setuptools` build backend).
  `setup.py` is now a one-line shim.
- Bumped `python_requires` to `>=3.9` to match the CI test matrix and
  Pydantic v2 requirements.
- Added `[project.optional-dependencies] lint` (ruff + black + mypy)
  and pre-configured `[tool.ruff]`, `[tool.black]`, `[tool.mypy]`.
- FastAPI minimum bumped to `>=0.110` to align with Pydantic v2 support.

## Migration notes

Applications using the recommended Pydantic v2 schemas need no code
changes. If you still have v1 schemas, they continue to work via the
`model_to_dict` shim, but you are encouraged to upgrade — Pydantic v1
is no longer in the test matrix.

PATCH endpoints now correctly preserve fields that the client did not
send. Previously every PATCH request silently included all default
values, which sometimes overwrote rows with default data. The new
behavior matches REST/DRF expectations.

## Tests

- 236 / 244 tests pass on CPython 3.12 (the 8 skipped failures are
  pre-existing Tortoise/Peewee issues caused by upstream library
  changes — see issues for tracking).
- Coverage: **83%** (above the 70% gate).
