# Release v1.4.0

## ✨ What's New

Official support for **Python 3.14**, plus dependency bounds that keep the
optional ORM adapters on known-compatible major versions.

## 🐍 Python 3.14 Support

- `pyproject.toml` now declares `Programming Language :: Python :: 3.14`, so
  PyPI and the version badge reflect the new interpreter.
- The CI test matrix runs on Python 3.9 – 3.14.
- `black` `target-version` extended with `py314`.
- The full test suite (263 tests) passes on Python 3.14.3 with current
  dependency versions: FastAPI 0.141, Pydantic 2.12, SQLAlchemy 2.0.52.

## 📦 Dependency Bounds

- `tortoise` extra: `tortoise-orm>=0.20.0,<1.0` — Tortoise ORM 1.x introduces
  breaking API changes (`TortoiseContext`, removal of implicit global state)
  that are not compatible with this adapter yet.
- `peewee` extra: `peewee>=3.17.0,<4` — Peewee 4.x changes exception
  behaviour of `ModelSelect.get()` (raw `IndexError` instead of
  `DoesNotExist`), which breaks adapters and tests.
- Core dependencies are unchanged (`fastapi>=0.110`, `pydantic>=2.5,<3`,
  `SQLAlchemy>=1.4.36`) — current releases of all of them already support
  Python 3.14.

## 🧪 Testing

- Fixed previously broken Tortoise adapter tests: models are now properly
  registered through `models=["tests.tortoise_models"]` instead of relying
  on unregistered locally-defined models, and schemas are generated with
  `Tortoise.generate_schemas(safe=True)`.
- Fixed the Peewee `delete_element` test to expect `DoesNotExist` after
  deletion instead of a `None` return from `get_by_id()`.
- New CI job `test-extras` runs the suite with the `tortoise` and `peewee`
  extras installed on Python 3.14, so adapter tests are no longer skipped
  in CI.

## 📦 Installation

```bash
pip install fastapi-viewsets
```

---

**Full Changelog**: https://github.com/svalench/fastapi_viewsets/compare/v1.3.0...v1.4.0
