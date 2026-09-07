# Release v1.5.0

## ✨ What's New

The two last "Roadmap" rows of the feature matrix are done: **server-side
search** and **declarative ordering with advanced filters** are now
supported across all four adapters.

## 🔎 Search, Ordering & Filters via `ListConfig`

Declare an inner `ListConfig` class on your Pydantic response schema and
the LIST endpoint gains query-parameter-driven search, ordering and
filtering — no viewset code changes needed:

```python
class ItemSchema(BaseModel):
    id: int
    name: str
    status: str

    class ListConfig:
        search_fields = ["name"]              # ?search=foo
        ordering_fields = ["name", "id"]      # ?ordering=-name,id
        ordering = ["-id"]                    # default ordering
        filters = ["status"]                  # ?status=active, ?status__in=a,b
```

- **`?search=term`** — case-insensitive substring match, OR-ed across
  `search_fields`.
- **`?ordering=-name,id`** — validated against `ordering_fields` (unknown
  field → `400`); the declarative `ordering` applies when the parameter
  is omitted.
- **Filters** — exact match plus operators `ne`, `gt`, `gte`, `lt`, `lte`,
  `contains`, `in`; values coerced to int/float/bool; only whitelisted
  fields ever reach the ORM.

Supported by **SQLAlchemy (sync & async), Tortoise ORM and Peewee**
adapters, on both `BaseViewset` and `AsyncBaseViewset`. The utility layer
(`get_list_queryset` in `utils` / `async_utils`) accepts the same
`search`, `search_fields`, `ordering`, `filters` arguments for
programmatic use.

## 🛡 Safety & Compatibility

- Field whitelists are enforced: unknown filter fields are ignored and
  unknown ordering fields return `400` — arbitrary column names never
  reach the ORM.
- Fully backward compatible: schemas without a `ListConfig` behave
  exactly as before (search/ordering parameters ignored).
- Custom adapters keep working — new arguments are only forwarded when
  actually used.

## 📚 Documentation

- `docs/pagination-filtering.md` rewritten around `ListConfig`.
- Feature matrix and roadmap updated in README and docs.

## 🧪 Testing

- New test suite `tests/test_search_ordering.py` (31 tests) covering
  config parsing, sync/async viewsets end-to-end, and Tortoise/Peewee
  adapter behaviour.
- 294 tests pass, coverage 88.5%.

---

**Full Changelog**: https://github.com/svalench/fastapi_viewsets/compare/v1.4.0...v1.5.0
