"""Exercise deletion policies through HTTP and real databases for every ORM."""

import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import pytest
from fastapi import FastAPI
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from fastapi_viewsets import AsyncBaseViewset, BaseViewset, SoftDeleteConfig


class ItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    name: str
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    class ListConfig:
        search_fields = ["name"]
        ordering_fields = ["id", "name"]
        ordering = ["id"]
        filters = ["is_deleted", "deleted_at", "name"]


@pytest.fixture(params=["sqlalchemy", "sqlalchemy-async", "peewee", "tortoise"])
def backend(request, tmp_path):
    name = request.param
    path = tmp_path / "items.db"
    if name.startswith("sqlalchemy"):
        from sqlalchemy import Boolean, Column, DateTime, Integer, String

        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter

        adapter = SQLAlchemyAdapter(database_url=f"sqlite:///{path}")
        base = adapter.get_base()

        class Item(base):
            __tablename__ = "soft_delete_items"
            id = Column(Integer, primary_key=True)
            name = Column(String, nullable=False)
            is_deleted = Column(Boolean, nullable=False, default=False)
            deleted_at = Column(DateTime(timezone=True), nullable=True)

        base.metadata.create_all(adapter.engine)
        session = adapter.get_async_session if name.endswith("async") else adapter.get_session
        viewset = AsyncBaseViewset if name.endswith("async") else BaseViewset
    elif name == "peewee":
        peewee = pytest.importorskip("peewee")
        from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter

        database = peewee.SqliteDatabase(str(path), check_same_thread=False)
        item_database = database

        class Item(peewee.Model):
            name = peewee.CharField()
            is_deleted = peewee.BooleanField(default=False)
            deleted_at = peewee.DateTimeField(null=True)

            class Meta:
                database = item_database
                table_name = "soft_delete_items"

        database.create_tables([Item])
        adapter = PeeweeAdapter(database_url=f"sqlite:///{path}", database=database)
        session = adapter.get_session
        viewset = BaseViewset
    else:
        pytest.importorskip("tortoise")
        from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
        from tests.tortoise_models import SoftDeleteItem as Item

        adapter = TortoiseAdapter(database_url=f"sqlite://{path}", models=["tests.tortoise_models"])
        session = adapter.get_async_session
        viewset = AsyncBaseViewset

    @asynccontextmanager
    async def lifespan(app):
        if name == "tortoise":
            await adapter.initialize(generate_schemas=True)
        try:
            yield
        finally:
            if name == "tortoise":
                await adapter.close()
            elif name.startswith("sqlalchemy") and adapter.async_engine:
                await adapter.async_engine.dispose()

    yield adapter, Item, session, viewset, path, lifespan
    if name.startswith("sqlalchemy"):
        adapter.engine.dispose()
    elif name == "peewee":
        database.close()


@pytest.fixture(params=["boolean", "timestamp"])
def policy(request):
    return SoftDeleteConfig(
        field="is_deleted" if request.param == "boolean" else "deleted_at", mode=request.param
    )


@pytest.fixture
def stack(backend, policy):
    adapter, model, session, viewset_class, path, lifespan = backend
    router = viewset_class(
        endpoint="/items",
        model=model,
        db_session=session,
        response_model=ItemSchema,
        orm_adapter=adapter,
        soft_delete=policy,
    )
    router.register(
        oauth_protect=OAuth2PasswordBearer(tokenUrl="/token"), protected_methods=["DELETE"]
    )
    legacy = viewset_class(
        endpoint="/legacy",
        model=model,
        db_session=session,
        response_model=ItemSchema,
        orm_adapter=adapter,
    )
    legacy.register(methods=["LIST", "GET", "DELETE"])
    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    app.include_router(legacy)
    with TestClient(app) as client:
        yield client, policy, path


AUTH = {"Authorization": "Bearer example"}


def create(client, name="apple", **extra):
    response = client.post("/items", json={"name": name, **extra})
    assert response.status_code == 200, response.text
    return response.json()["id"]


def stored_row(path, id):
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM soft_delete_items WHERE id = ?", (id,)).fetchone()
        return dict(row) if row is not None else None


def test_delete_filter_restore_cycle(stack):
    client, policy, path = stack
    id = create(client)
    url = f"/items/{id}"
    response = client.delete(url, headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": True, "text": "successfully deleted"}
    deleted = stored_row(path, id)
    assert deleted is not None
    assert deleted[policy.field] if policy.mode == "boolean" else deleted[policy.field] is not None
    assert client.get("/items").json() == []
    assert client.get(url).status_code == 404
    assert client.patch(url, json={"name": "changed"}).status_code == 404
    assert client.put(url, json={"name": "changed"}).status_code == 404
    assert client.delete(url, headers=AUTH).status_code == 404
    assert stored_row(path, id) == deleted

    # Config belongs to a viewset, not its shared adapter or model.
    assert len(client.get("/legacy").json()) == 1
    assert client.get(f"/legacy/{id}").status_code == 200
    response = client.post(url + "/restore", headers=AUTH)
    assert response.status_code == 200, response.text
    assert response.json() == {"status": True, "text": "successfully restored"}
    assert stored_row(path, id)[policy.field] == policy.active_value
    assert client.get(url).json()["name"] == "apple"
    assert len(client.get("/items").json()) == 1
    assert client.post(url + "/restore", headers=AUTH).status_code == 404
    assert client.post("/items/99999/restore", headers=AUTH).status_code == 404


def test_policy_cannot_be_overridden_by_query_or_body(stack):
    client, policy, path = stack
    malicious = True if policy.mode == "boolean" else "2026-01-01T00:00:00Z"
    id = create(client, **{policy.field: malicious})
    assert stored_row(path, id)[policy.field] == policy.active_value
    for method in ("put", "patch"):
        response = client.request(
            method, f"/items/{id}", json={"name": "updated", policy.field: malicious}
        )
        assert response.status_code == 200, response.text
        assert stored_row(path, id)[policy.field] == policy.active_value
    assert client.delete(f"/items/{id}", headers=AUTH).status_code == 200
    for query in (
        "is_deleted=true",
        "is_deleted__in=false,true",
        "deleted_at__ne=null",
        "include_deleted=true",
        "search=updated",
        "ordering=-id",
    ):
        response = client.get("/items?" + query)
        assert response.status_code == 200, response.text
        assert response.json() == []
    response = client.patch(f"/items/{id}", json={policy.field: policy.active_value})
    assert response.status_code == 404


def test_filter_before_pagination_and_legacy_hard_delete(stack):
    client, policy, path = stack
    first, second, third = [create(client, name) for name in ("first", "second", "third")]
    assert client.delete(f"/items/{first}", headers=AUTH).status_code == 200
    assert [row["id"] for row in client.get("/items?limit=1&offset=0").json()] == [second]
    assert [row["id"] for row in client.get("/items?limit=1&offset=1").json()] == [third]
    assert client.get("/items?limit=0").json() == []
    response = client.delete(f"/legacy/{first}")
    assert response.status_code == 200, response.text
    assert stored_row(path, first) is None
    assert client.post(f"/items/{first}/restore", headers=AUTH).status_code == 404
    assert client.post(f"/legacy/{second}/restore").status_code == 404


def test_restore_inherits_delete_auth_and_openapi(stack):
    client, policy, path = stack
    id = create(client)
    assert client.delete(f"/items/{id}").status_code == 401
    assert client.delete(f"/items/{id}", headers=AUTH).status_code == 200
    assert client.post(f"/items/{id}/restore").status_code == 401
    assert client.post(f"/items/{id}/restore?token=anything").status_code == 401
    assert stored_row(path, id)[policy.field] != policy.active_value
    paths = client.get("/openapi.json").json()["paths"]
    restore = paths["/items/{id}/restore"]["post"]
    assert restore["security"] == paths["/items/{id}"]["delete"]["security"]
    assert "requestBody" not in restore
    assert "/legacy/{id}/restore" not in paths


def test_restore_conflict_rolls_back_without_leaking_database_details(stack):
    client, policy, path = stack
    predicate = "is_deleted = 0" if policy.mode == "boolean" else "deleted_at IS NULL"
    with sqlite3.connect(path) as connection:
        connection.execute(
            f"CREATE UNIQUE INDEX active_name ON soft_delete_items(name) WHERE {predicate}"
        )
    id = create(client)
    assert client.delete(f"/items/{id}", headers=AUTH).status_code == 200
    create(client)
    deleted = stored_row(path, id)
    response = client.post(f"/items/{id}/restore", headers=AUTH)
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "Integrity error: a database constraint was violated"}
    assert stored_row(path, id) == deleted
    assert len(client.get("/items").json()) == 1


@pytest.mark.parametrize("kwargs", [{"field": ""}, {"field": "_hidden"}, {"mode": "invalid"}])
def test_invalid_config(kwargs):
    with pytest.raises(ValueError):
        SoftDeleteConfig(**kwargs)


def test_bad_model_configuration_fails_early(backend):
    adapter, model, session, viewset, path, lifespan = backend
    for policy in (
        SoftDeleteConfig(field="missing"),
        SoftDeleteConfig(field="id"),
        SoftDeleteConfig(field="name"),
        SoftDeleteConfig(field="name", mode="timestamp"),
    ):
        with pytest.raises(ValueError):
            viewset(model=model, orm_adapter=adapter, soft_delete=policy)


def test_restore_registration_is_opt_in_and_respects_selected_methods(backend):
    adapter, model, session, viewset, path, lifespan = backend
    router = viewset(
        endpoint="/items",
        model=model,
        orm_adapter=adapter,
        response_model=ItemSchema,
        soft_delete=SoftDeleteConfig(),
    )
    router.register(methods=["LIST"])
    assert len(router.routes) == 1
    router.register(methods=["RESTORE"])
    assert router.routes[-1].path == "/items/{id}/restore"
    legacy = viewset(endpoint="/legacy", model=model, orm_adapter=adapter)
    with pytest.raises(ValueError, match="RESTORE requires"):
        legacy.register(methods=["RESTORE"])


def test_existing_custom_adapter_does_not_need_soft_delete_methods():
    from fastapi_viewsets.orm.base import BaseORMAdapter

    class LegacySchema(BaseModel):
        id: int
        name: str

    class LegacyAdapter(BaseORMAdapter):
        # Only the original abstract interface is implemented. No new keyword
        # arguments are accepted by these read methods.
        def get_list_queryset(
            self, model, db_session, limit, offset, select_related=None, prefetch_related=None
        ):
            return []

        def get_element_by_id(
            self, model, db_session, id, select_related=None, prefetch_related=None
        ):
            return {"id": id, "name": "legacy"}

    def original_method(self, *args, **kwargs):
        return None

    # Provide exactly the pre-existing abstract methods. RESTORE must remain
    # optional, otherwise an installed custom adapter would stop instantiating.
    original_abstracts = {
        "get_session",
        "get_async_session",
        "get_base",
        "get_list_queryset",
        "get_list_queryset_async",
        "get_element_by_id",
        "get_element_by_id_async",
        "create_element",
        "create_element_async",
        "update_element",
        "update_element_async",
        "delete_element",
        "delete_element_async",
        "get_model_columns",
    }
    methods = {
        name: original_method
        for name in original_abstracts
        if name not in {"get_list_queryset", "get_element_by_id"}
    }
    adapter = type("InstalledAdapter", (LegacyAdapter,), methods)()
    router = BaseViewset(
        endpoint="/legacy", model=object, orm_adapter=adapter, response_model=LegacySchema
    )
    router.register(methods=["LIST", "GET"])
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/legacy").json() == []
        assert client.get("/legacy/1").json()["name"] == "legacy"
    with pytest.raises(ValueError, match="does not support"):
        BaseViewset(model=object, orm_adapter=adapter, soft_delete=SoftDeleteConfig())
