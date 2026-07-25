# Comparison with Alternatives

## Why fastapi-viewsets

`fastapi-viewsets` brings Django REST Framework-style ergonomics to FastAPI: define a model and a schema, call `register()`, and get a full CRUD API with pagination, OAuth2, and OpenAPI docs — all type-safe with Pydantic v2.

## Feature comparison

| Approach | Developer experience | ORM support | Permissions | Filtering |
| --- | --- | --- | --- | --- |
| **fastapi-viewsets** | One `BaseViewset` registers CRUD routes | SQLAlchemy sync/async, Tortoise, Peewee via adapters | OAuth2 per logical method via `register` | `limit`/`offset` today; `search` and advanced filters on Roadmap |
| fastapi-crudrouter | CRUD-focused generators, less ViewSet-shaped | SQLAlchemy, Tortoise, Ormar, Gino, databases | Custom middleware/deps | Often extended manually |
| Hand-rolled FastAPI | Full control, most boilerplate | Any ORM you integrate | Fully custom | Fully custom |

## When to use fastapi-viewsets

**Good fit if you:**

- Want DRF-style declarative CRUD without boilerplate
- Use SQLAlchemy (sync or async), Tortoise ORM, or Peewee
- Need Pydantic v2 type safety with OpenAPI auto-generation
- Want declarative eager loading to eliminate N+1 queries
- Need OAuth2 on specific methods (e.g. reads public, writes protected)

**Consider alternatives if you:**

- Need complex filtering, ordering, or search out of the box (these are on the [roadmap](#roadmap) but not yet built)
- Use an ORM without an adapter (e.g. SQLModel, Beanie) — though you can write a custom `BaseORMAdapter`
- Need a full permissions framework with role-based access control

## Declarative eager loading

A unique feature of `fastapi-viewsets` is the `RelatedConfig` class on Pydantic schemas, which eliminates N+1 queries without touching the viewset:

```python
class PostSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    author: AuthorSchema

    class RelatedConfig:
        select_related = ["author"]    # FK → single JOIN
        prefetch_related = ["tags"]    # M2M → separate SELECT IN
```

A key differentiator of `fastapi-viewsets` is the schema-driven approach to eager loading via `RelatedConfig` — you declare eager-loading strategy on the Pydantic schema, not on the viewset or query.

## ORM adapter architecture

The adapter pattern means you can switch ORMs by changing one environment variable:

```dotenv
ORM_TYPE=sqlalchemy   # or "tortoise" or "peewee"
```

Each adapter implements the same `BaseORMAdapter` interface, so viewset code stays identical regardless of the ORM. You can also create adapters programmatically without environment variables using `ORMFactory.create_adapter()`.

## Roadmap

| Item | Target | Status |
| --- | --- | --- |
| Wire `search` on LIST to real database queries | v1.4 | Planned |
| Transaction helpers (`begin` / `atomic`) across adapters | v1.4 | Planned |
| Declarative ordering (`order_by`) on LIST endpoints | v1.4 | Planned |
| Advanced filters (`__gt`, `__lt`, `__in`) via query params | v1.5 | Planned |
