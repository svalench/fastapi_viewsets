# Release 1.2.1 — async driver fallback hotfix

Bugfix release for v1.2.0.

## What changed

### Fixed
- **Crash at adapter init when async DB driver is missing.** Since v1.2.0 the
  default `SQLAlchemyAdapter` was always created with an explicit
  `async_database_url`, which caused `create_async_engine()` to raise
  `ModuleNotFoundError: No module named 'aiosqlite'` (or `asyncpg` /
  `aiomysql`) at construction time, breaking purely-synchronous setups.

  Now the adapter degrades gracefully: if the async DB-API driver is not
  installed, `async_engine` and `AsyncSessionLocal` fall back to `None` and
  `get_async_session()` raises a helpful `RuntimeError` explaining which
  package to install. Sync usage continues to work without any extra
  dependency.

### Internal
- Switched packaging in `pyproject.toml` from a hard-coded package list to
  `[tool.setuptools.packages.find]`, so any future subpackages are picked up
  automatically by the wheel/sdist build.
- Added regression tests covering both the explicit-URL and auto-converted-URL
  paths when `aiosqlite` is missing.

## Upgrade

```bash
pip install -U fastapi-viewsets==1.2.1
```

No code changes are required. If you want full async support, install the
matching driver:

```bash
pip install aiosqlite     # SQLite
pip install asyncpg       # PostgreSQL
pip install aiomysql      # MySQL
```
