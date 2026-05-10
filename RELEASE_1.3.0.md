# Release 1.3.0 — Declarative eager loading (`select_related` / `prefetch_related`)

This release introduces a Django-like way to eliminate N+1 queries: an inner
`RelatedConfig` class on Pydantic schemas that tells the ORM adapter which
relationships to eager-load on `LIST` and `GET` endpoints.

## Highlights

### Declarative eager loading via `RelatedConfig`

- Add `select_related = [...]` (FK / many-to-one) and/or
  `prefetch_related = [...]` (collections / many-to-many) to a Pydantic
  schema's inner `RelatedConfig` class.
- When the schema is used as `response_model` in a viewset, `BaseViewset`
  and `AsyncBaseViewset` automatically forward these lists to the ORM
  adapter so relationships are loaded in a single (or minimal) round-trip.
- No changes in the viewset itself are required — configuration lives in the
  schema, next to the fields it describes.

**Example:**

```python
class PostSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    author: AuthorSchema          # nested → needs join

    class RelatedConfig:
        select_related = ["author"]   # SQLAlchemy: joinedload
        prefetch_related = ["tags"]   # SQLAlchemy: selectinload
```

```python
posts = AsyncBaseViewset(
    endpoint="/posts",
    model=Post,
    response_model=PostSchema,
    db_session=get_async_session,
)
```

### Adapter-level support

| ORM | `select_related` | `prefetch_related` | Implementation |
| --- | --- | --- | --- |
| **SQLAlchemy (sync)** | ✅ | ✅ | `joinedload` / `selectinload` on `Query` |
| **SQLAlchemy (async)** | ✅ | ✅ | `joinedload` / `selectinload` on `select()` + `result.unique()` |
| **Tortoise ORM** | ✅* | ✅ | `prefetch_related()` for both (*Tortoise has no separate `select_related`) |
| **Peewee** | ✅ | — | `.join()` for `select_related` |

- All adapter methods (`get_list_queryset`, `get_list_queryset_async`,
  `get_element_by_id`, `get_element_by_id_async`) accept optional
  `select_related` and `prefetch_related` keyword arguments for explicit
  overrides.
- The low-level utilities in `fastapi_viewsets.utils` and
  `fastapi_viewsets.async_utils` also accept these arguments, plus an
  optional `response_model`. When `response_model` is provided and the
  explicit lists are omitted, the utilities read them automatically from
  `RelatedConfig`.

### Backward compatibility

- Every new parameter defaults to `None`. Existing code, tests and
  subclassed viewsets continue to work without any changes.
- The public API surface of `BaseViewset` and `AsyncBaseViewset` is
  unchanged; only the internal calls to the ORM adapters now forward
  additional optional kwargs.

## Internal additions

- `fastapi_viewsets.serializer_utils` — small helper module that extracts
  `select_related` and `prefetch_related` from a Pydantic model's
  `RelatedConfig` inner class.

## Tests

- 258+ tests pass (219 new/legacy + 39 skipped for optional ORMs).
- Coverage remains above the 70% gate.
- New dedicated test file: `tests/test_select_prefetch_related.py` covering
  `serializer_utils`, SQLAlchemy sync/async adapters, and the integration
  between `utils` / `async_utils` with `RelatedConfig`.

## Upgrade

```bash
pip install -U fastapi-viewsets==1.3.0
```

No code changes are required for existing users. To opt into eager loading,
add a `RelatedConfig` class to the Pydantic schemas you already pass as
`response_model`.
