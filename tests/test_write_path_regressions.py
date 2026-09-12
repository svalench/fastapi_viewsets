"""Regression tests for CRUD write-path bugs fixed in 1.5.2.

Covers:
* B1 — body-schema annotations must not leak between viewsets.
* B2 — PATCH accepts partial bodies even when the schema has required fields.
* B4 — PATCH honors explicit JSON ``null`` (clears nullable columns).
* B3 — PUT never nulls columns absent from the Pydantic schema.
* B5 — ``id: Optional[int] = None`` in the schema must not break create.
* B6 — integrity violations return 409 without raw SQL internals.
* M2 — negative ``limit``/``offset`` are rejected with 422.
* M5 — whitelisted filters appear in the OpenAPI schema.
"""

from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field


@pytest.fixture()
def sqlalchemy_stack(tmp_path):
    from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter

    adapter = SQLAlchemyAdapter(database_url=f"sqlite:///{tmp_path}/reg.db")
    yield adapter
    adapter.engine.dispose()


def _make_model(adapter, tablename, extra_column=False):
    from sqlalchemy import Column, Integer, String

    Base = adapter.get_base()

    class RegModel(Base):
        __tablename__ = tablename
        id = Column(Integer, primary_key=True)
        name = Column(String(255), nullable=False, unique=True)
        price = Column(Integer, nullable=True)
        if extra_column:
            secret = Column(String(255), nullable=True)

    Base.metadata.create_all(adapter.engine)
    return RegModel


class _NameSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    name: str = Field(min_length=1, max_length=255)
    price: Optional[int] = None


class _TitleSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    title: str = Field(min_length=1, max_length=255)


def _build_two_viewset_app(adapter):
    """Two viewsets with different schemas in one process (B1 repro)."""
    from sqlalchemy import Column, Integer, String

    from fastapi_viewsets import BaseViewset

    Base = adapter.get_base()

    class Alpha(Base):
        __tablename__ = "reg_alpha"
        id = Column(Integer, primary_key=True)
        name = Column(String(255), nullable=False)
        price = Column(Integer, nullable=True)

    class Beta(Base):
        __tablename__ = "reg_beta"
        id = Column(Integer, primary_key=True)
        title = Column(String(255), nullable=False)
        price = Column(Integer, nullable=True)

    Base.metadata.create_all(adapter.engine)

    app = FastAPI()
    va = BaseViewset(
        endpoint="/alpha",
        model=Alpha,
        response_model=_NameSchema,
        db_session=adapter.get_session,
        orm_adapter=adapter,
    )
    va.register(methods=["POST", "PATCH"])
    vb = BaseViewset(
        endpoint="/beta",
        model=Beta,
        response_model=_TitleSchema,
        db_session=adapter.get_session,
        orm_adapter=adapter,
    )
    vb.register(methods=["POST", "PATCH"])
    app.include_router(va)
    app.include_router(vb)
    return app


def test_b1_schemas_do_not_leak_between_viewsets(sqlalchemy_stack):
    """Each viewset validates against its own response_model."""
    app = _build_two_viewset_app(sqlalchemy_stack)
    client = TestClient(app)

    r = client.post("/alpha", json={"name": "hello", "price": 1})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "hello"

    r = client.post("/beta", json={"title": "world"})
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "world"

    # wrong schema is rejected on both endpoints
    assert client.post("/alpha", json={"title": "x"}).status_code == 422
    assert client.post("/beta", json={"name": "x"}).status_code == 422


def test_b2_patch_accepts_partial_body_with_required_fields(sqlalchemy_stack):
    """PATCH must not require fields the client did not intend to change."""
    from fastapi_viewsets import BaseViewset

    model = _make_model(sqlalchemy_stack, "reg_patch_partial")
    app = FastAPI()
    vs = BaseViewset(
        endpoint="/items",
        model=model,
        response_model=_NameSchema,
        db_session=sqlalchemy_stack.get_session,
        orm_adapter=sqlalchemy_stack,
    )
    vs.register(methods=["POST", "PATCH"])
    app.include_router(vs)
    client = TestClient(app)

    created = client.post("/items", json={"name": "patchme", "price": 100}).json()
    r = client.patch(f"/items/{created['id']}", json={"price": 777})
    assert r.status_code == 200, r.text
    assert r.json()["price"] == 777
    assert r.json()["name"] == "patchme"


def test_b4_patch_explicit_null_clears_field(sqlalchemy_stack):
    """Explicit JSON null clears a nullable column (not silently ignored)."""
    from fastapi_viewsets import BaseViewset

    model = _make_model(sqlalchemy_stack, "reg_patch_null")
    app = FastAPI()
    vs = BaseViewset(
        endpoint="/items",
        model=model,
        response_model=_NameSchema,
        db_session=sqlalchemy_stack.get_session,
        orm_adapter=sqlalchemy_stack,
    )
    vs.register(methods=["POST", "PATCH"])
    app.include_router(vs)
    client = TestClient(app)

    created = client.post("/items", json={"name": "nullme", "price": 50}).json()
    r = client.patch(f"/items/{created['id']}", json={"price": None})
    assert r.status_code == 200, r.text
    assert r.json()["price"] is None


def test_b3_put_preserves_columns_absent_from_schema(sqlalchemy_stack):
    """PUT must not null out model columns missing from the schema."""
    from sqlalchemy import text

    from fastapi_viewsets import BaseViewset

    model = _make_model(sqlalchemy_stack, "reg_put_secret", extra_column=True)
    app = FastAPI()
    vs = BaseViewset(
        endpoint="/items",
        model=model,
        response_model=_NameSchema,
        db_session=sqlalchemy_stack.get_session,
        orm_adapter=sqlalchemy_stack,
    )
    vs.register(methods=["POST", "PUT"])
    app.include_router(vs)
    client = TestClient(app)

    created = client.post("/items", json={"name": "keepsecret", "price": 1}).json()
    db = sqlalchemy_stack.get_session()
    db.execute(
        text("UPDATE reg_put_secret SET secret='classified' WHERE id=:i"), {"i": created["id"]}
    )
    db.commit()
    db.close()

    r = client.put(f"/items/{created['id']}", json={"name": "renamed", "price": 2})
    assert r.status_code == 200, r.text

    db = sqlalchemy_stack.get_session()
    secret = db.execute(
        text("SELECT secret FROM reg_put_secret WHERE id=:i"), {"i": created["id"]}
    ).scalar()
    db.close()
    assert secret == "classified"


def test_b5_create_ignores_none_primary_key(sqlalchemy_stack):
    """Schemas with ``id: Optional[int] = None`` must not break create."""
    from fastapi_viewsets import BaseViewset

    model = _make_model(sqlalchemy_stack, "reg_pk_none")
    app = FastAPI()
    vs = BaseViewset(
        endpoint="/items",
        model=model,
        response_model=_NameSchema,
        db_session=sqlalchemy_stack.get_session,
        orm_adapter=sqlalchemy_stack,
    )
    vs.register(methods=["POST"])
    app.include_router(vs)
    client = TestClient(app)

    r = client.post("/items", json={"id": None, "name": "auto", "price": 3})
    assert r.status_code == 200, r.text
    assert r.json()["id"] is not None


def test_b6_integrity_error_is_409_without_sql_leak(sqlalchemy_stack):
    """Duplicate unique value -> 409, no SQL/driver internals in detail."""
    from fastapi_viewsets import BaseViewset

    model = _make_model(sqlalchemy_stack, "reg_conflict")
    app = FastAPI()
    vs = BaseViewset(
        endpoint="/items",
        model=model,
        response_model=_NameSchema,
        db_session=sqlalchemy_stack.get_session,
        orm_adapter=sqlalchemy_stack,
    )
    vs.register(methods=["POST"])
    app.include_router(vs)
    client = TestClient(app)

    assert client.post("/items", json={"name": "dup"}).status_code == 200
    r = client.post("/items", json={"name": "dup"})
    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert "sqlite3" not in detail
    assert "IntegrityError" not in detail
    assert "INSERT" not in detail.upper()


def test_m2_negative_pagination_rejected(sqlalchemy_stack):
    """limit/offset below zero must be rejected with 422."""
    from fastapi_viewsets import BaseViewset

    model = _make_model(sqlalchemy_stack, "reg_pagination")
    app = FastAPI()
    vs = BaseViewset(
        endpoint="/items",
        model=model,
        response_model=_NameSchema,
        db_session=sqlalchemy_stack.get_session,
        orm_adapter=sqlalchemy_stack,
    )
    vs.register(methods=["LIST"])
    app.include_router(vs)
    client = TestClient(app)

    assert client.get("/items?limit=-5").status_code == 422
    assert client.get("/items?offset=-10").status_code == 422


def test_m5_filters_documented_in_openapi(sqlalchemy_stack):
    """Whitelisted ListConfig filters are advertised in OpenAPI."""
    from fastapi_viewsets import BaseViewset

    class FilterSchema(_NameSchema):
        class ListConfig:
            filters = ["price"]

    model = _make_model(sqlalchemy_stack, "reg_openapi_filters")
    app = FastAPI()
    vs = BaseViewset(
        endpoint="/items",
        model=model,
        response_model=FilterSchema,
        db_session=sqlalchemy_stack.get_session,
        orm_adapter=sqlalchemy_stack,
    )
    vs.register(methods=["LIST"])
    app.include_router(vs)
    client = TestClient(app)

    spec = client.get("/openapi.json").json()
    params = {p["name"] for p in spec["paths"]["/items"]["get"].get("parameters", [])}
    assert "price" in params
    assert "price__gte" in params
    assert "price__in" in params


@pytest.mark.asyncio
async def test_b5_tortoise_create_with_none_pk(tmp_path):
    """Tortoise adapter create strips an explicit None primary key."""
    pytest.importorskip("tortoise")
    from tortoise import Tortoise

    from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter

    # File-backed DB: the adapter and the schema generator each open
    # their own connection, and ``:memory:`` databases are per-connection.
    db_url = f"sqlite://{tmp_path}/tortoise_reg.db"

    adapter = TortoiseAdapter(
        database_url=db_url,
        models=["tests.test_write_path_regressions"],
        app_label="regressions",
    )
    await Tortoise.init(
        db_url=db_url,
        modules={"regressions": ["tests.test_write_path_regressions"]},
    )
    await Tortoise.generate_schemas(safe=True)
    try:
        obj = await adapter.create_element_async(
            RegTortoiseModel, adapter.get_async_session, {"id": None, "name": "t1"}
        )
        assert obj.id is not None
        assert obj.name == "t1"
    finally:
        await Tortoise.close_connections()


try:
    from tortoise import fields
    from tortoise.models import Model as _TortoiseModel

    class RegTortoiseModel(_TortoiseModel):
        id = fields.IntField(pk=True)
        name = fields.CharField(max_length=255, unique=True)

        class Meta:
            app = "regressions"

except ImportError:  # pragma: no cover - tortoise optional
    RegTortoiseModel = None


# --- Coverage for the non-bound-method fallback in _register.py --------


class _CustomPostHandler:
    """A POST handler that is not a plain bound method (callable object).

    ``register()`` must fall back to best-effort annotation patching on
    the handler object itself instead of cloning the function.
    """

    __annotations__ = {"item": "ItemSchema"}

    def __call__(self, item=None, token=None):
        return {"status": True, "text": "created"}


class _UnpatchablePostHandler(_CustomPostHandler):
    """A callable whose ``__annotations__`` cannot be reassigned.

    Registration must still succeed (patching is best-effort).
    """

    @property
    def __annotations__(self):  # noqa: N805 - instance-level property
        return {"item": "ItemSchema"}


def test_register_patches_non_bound_method_handler():
    """Callable-object handlers get the body schema merged into their
    own annotations without breaking registration."""
    from fastapi_viewsets import BaseViewset

    vs = BaseViewset(endpoint="/custom", model=None, response_model=_NameSchema)
    handler = _CustomPostHandler()
    vs.create_element = handler

    vs.register(methods=["POST"])

    assert handler.__annotations__["item"] is _NameSchema
    assert any(getattr(r, "path", None) == "/custom" for r in vs.routes)


def test_register_tolerates_unpatchable_non_bound_method_handler():
    """Best-effort patching: even a handler that rejects annotation
    assignment must leave register() working."""
    from fastapi_viewsets import BaseViewset

    vs = BaseViewset(endpoint="/other", model=None, response_model=_NameSchema)
    handler = _UnpatchablePostHandler()
    vs.create_element = handler

    vs.register(methods=["POST"])  # must not raise

    # the untouched property still serves the original annotations
    assert handler.__annotations__ == {"item": "ItemSchema"}
    assert any(getattr(r, "path", None) == "/other" for r in vs.routes)


# --- Coverage for the Query-default fallback in list() -----------------


def test_m6_programmatic_list_non_int_pagination(test_model, test_schema, db_session_factory):
    """Direct programmatic ``list()`` calls receive the unresolved
    ``Query`` defaults; the handler must fall back to sane values (sync)."""
    from fastapi_viewsets import BaseViewset

    vs = BaseViewset(
        endpoint="/test",
        model=test_model,
        response_model=test_schema,
        db_session=db_session_factory,
        tags=["Test"],
    )

    # no kwargs: limit/offset arrive as Query(...) objects, not ints
    result = vs.list()
    assert isinstance(result, list)


@pytest.mark.asyncio
async def test_m6_programmatic_async_list_non_int_pagination(
    test_model, test_schema, async_db_session_factory
):
    """Same fallback for ``AsyncBaseViewset.list``."""
    from fastapi_viewsets import AsyncBaseViewset

    vs = AsyncBaseViewset(
        endpoint="/test",
        model=test_model,
        response_model=test_schema,
        db_session=async_db_session_factory,
        tags=["Test"],
    )

    result = await vs.list()
    assert isinstance(result, list)
