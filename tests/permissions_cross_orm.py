"""HTTP-тесты permission_classes на SQLAlchemy, Peewee и Tortoise."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, Callable, Dict, Optional, Type

import pytest
from fastapi import FastAPI, Header, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict
from typing import Optional as OptionalType

from fastapi_viewsets import (
    AsyncBaseViewset,
    BaseViewset,
    IsAuthenticated,
    IsAdminUser,
    IsOwner,
    NestedConfig,
    SoftDeleteConfig,
    init_permissions,
)
from tests.permissions_contracts import (
    assert_foreign_owner_id_is_404,
    assert_owner_list_is_scoped,
    assert_plain_viewset_has_no_auth_gate,
    assert_post_binds_current_owner,
    assert_staff_sees_all,
    assert_unauthenticated_forbidden,
)


USERS = {
    1: SimpleNamespace(id=1, username="alice", is_staff=False),
    2: SimpleNamespace(id=2, username="bob", is_staff=False),
    3: SimpleNamespace(id=3, username="staff", is_staff=True),
}


def auth_dependency(
    request: Request, x_user_id: OptionalType[int] = Header(default=None, alias="X-User-Id")
):
    user = USERS.get(x_user_id) if x_user_id is not None else None
    request.state.user = user
    return user


class OwnedSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: OptionalType[int] = None
    title: str
    user_id: OptionalType[int] = None


class FolderSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: OptionalType[int] = None
    title: str


class DocumentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: OptionalType[int] = None
    title: str
    folder_id: OptionalType[int] = None
    user_id: OptionalType[int] = None


def _headers(user_id: int) -> Dict[str, str]:
    return {"X-User-Id": str(user_id)}


async def _seed_perm_accounts(models) -> None:
    await models.PermAccount.get_or_create(id=1, defaults={"username": "alice", "is_staff": False})
    await models.PermAccount.get_or_create(id=2, defaults={"username": "bob", "is_staff": False})
    await models.PermAccount.get_or_create(id=3, defaults={"username": "staff", "is_staff": True})


def _app_with_tortoise_lifespan(adapter, owned: Dict[str, int], *, after_seed=None):
    """Единая точка init/close Tortoise для HTTP-тестов (без asyncio.run в фикстуре)."""

    @asynccontextmanager
    async def lifespan(app):
        from tests import permissions_tortoise_models as models

        await adapter.initialize(generate_schemas=True)
        await _seed_perm_accounts(models)
        if after_seed is not None:
            await after_seed(models)
        else:
            if not await models.PermOwnedItem.exists():
                await models.PermOwnedItem.create(title="a1", user_id=1)
                await models.PermOwnedItem.create(title="b1", user_id=2)
            owned.clear()
            for row in await models.PermOwnedItem.all():
                owned[row.title] = row.id
        try:
            yield
        finally:
            await adapter.close()

    return FastAPI(lifespan=lifespan)


@pytest.fixture(params=["sqlalchemy", "peewee", "tortoise"])
def owner_backend(request, tmp_path):
    name = request.param
    path = tmp_path / f"perm_{name}.db"
    user_model = None
    item_model = None
    adapter = None
    session = None
    viewset_class = BaseViewset
    owned: Dict[str, int] = {}
    pw_db = None

    if name == "sqlalchemy":
        from sqlalchemy import Boolean, Column, ForeignKey, Integer, String

        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter

        adapter = SQLAlchemyAdapter(database_url=f"sqlite:///{path}")
        base = adapter.get_base()

        class User(base):
            __tablename__ = "perm_x_accounts"
            id = Column(Integer, primary_key=True)
            username = Column(String, nullable=False)
            is_staff = Column(Boolean, default=False)

        class OwnedItem(base):
            __tablename__ = "perm_x_items"
            id = Column(Integer, primary_key=True)
            title = Column(String, nullable=False)
            user_id = Column(Integer, ForeignKey("perm_x_accounts.id"), nullable=False)
            is_deleted = Column(Boolean, default=False)

        base.metadata.create_all(adapter.engine)
        user_model, item_model = User, OwnedItem
        session = adapter.get_session
        db = session()
        db.add_all(
            [
                User(id=1, username="alice"),
                User(id=2, username="bob"),
                User(id=3, username="staff", is_staff=True),
                OwnedItem(title="a1", user_id=1),
                OwnedItem(title="b1", user_id=2),
            ]
        )
        db.commit()
        for row in db.query(OwnedItem).all():
            owned[row.title] = row.id
        db.close()

    elif name == "peewee":
        pw = pytest.importorskip("peewee")
        from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter

        pw_db = pw.SqliteDatabase(str(path), pragmas={"foreign_keys": 1})

        class User(pw.Model):
            id = pw.AutoField()
            username = pw.TextField()
            is_staff = pw.BooleanField(default=False)

            class Meta:
                database = pw_db
                table_name = "perm_x_accounts"

        class OwnedItem(pw.Model):
            id = pw.AutoField()
            title = pw.TextField()
            owner = pw.ForeignKeyField(User, backref="items")
            is_deleted = pw.BooleanField(default=False)

            class Meta:
                database = pw_db
                table_name = "perm_x_items"

        pw_db.create_tables([User, OwnedItem])
        adapter = PeeweeAdapter(database_url=f"sqlite:///{path}", database=pw_db)
        user_model, item_model = User, OwnedItem
        session = adapter.get_session
        u1 = User.create(id=1, username="alice")
        User.create(id=2, username="bob")
        User.create(id=3, username="staff", is_staff=True)
        owned["a1"] = OwnedItem.create(title="a1", owner=u1).id
        owned["b1"] = OwnedItem.create(title="b1", owner=User.get_by_id(2)).id

    else:
        pytest.importorskip("tortoise")
        from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
        from tests import permissions_tortoise_models as models

        adapter = TortoiseAdapter(
            database_url=f"sqlite://{path}",
            models=["tests.permissions_tortoise_models"],
        )
        user_model, item_model = models.PermAccount, models.PermOwnedItem
        session = adapter.get_async_session
        viewset_class = AsyncBaseViewset

    stack = {
        "name": name,
        "adapter": adapter,
        "session": session,
        "viewset_class": viewset_class,
        "user_model": user_model,
        "item_model": item_model,
        "owned": owned,
    }
    yield stack
    if name == "sqlalchemy":
        adapter.engine.dispose()
    elif name == "peewee":
        pw_db.close()
    else:
        asyncio.run(adapter.close())


def _build_owned_client(backend):
    owned = dict(backend["owned"])
    init_permissions(user_model=backend["user_model"])

    if backend["name"] == "tortoise":
        app = _app_with_tortoise_lifespan(backend["adapter"], owned)
    else:
        app = FastAPI()

    class Items(backend["viewset_class"]):
        permission_classes = [IsAuthenticated, IsOwner]

    router = Items(
        endpoint="/items",
        model=backend["item_model"],
        response_model=OwnedSchema,
        db_session=backend["session"],
        orm_adapter=backend["adapter"],
    )
    router.register(
        methods=["LIST", "GET", "POST", "PUT", "PATCH", "DELETE"],
        auth_dependency=auth_dependency,
    )
    app.include_router(router)
    return TestClient(app), owned


@pytest.fixture
def owner_client(owner_backend):
    client, owned = _build_owned_client(owner_backend)
    with client:
        yield client, owned, owner_backend


def test_cross_orm_unauthenticated_is_forbidden(owner_client):
    client, _, _ = owner_client
    assert_unauthenticated_forbidden(client, "/items")


def test_cross_orm_owner_list_and_foreign_id_404(owner_client):
    client, owned, backend = owner_client
    headers = _headers(2)
    assert_owner_list_is_scoped(client, "/items", headers, own_title="b1")
    assert client.get(f"/items/{owned['b1']}", headers=headers).status_code == 200
    assert_foreign_owner_id_is_404(client, "/items", owned["a1"], headers)


def test_cross_orm_post_binds_owner(owner_client):
    client, _, backend = owner_client
    owner_key = "owner_id" if backend["name"] == "peewee" else "user_id"
    assert_post_binds_current_owner(client, "/items", _headers(2), owner_key=owner_key)


def test_cross_orm_staff_bypass(owner_client):
    client, owned, _ = owner_client
    assert_staff_sees_all(client, "/items", owned, _headers(3))


def test_cross_orm_admin_only_viewset(owner_backend):
    backend = owner_backend
    init_permissions(user_model=backend["user_model"])
    app = (
        _app_with_tortoise_lifespan(backend["adapter"], backend["owned"])
        if backend["name"] == "tortoise"
        else FastAPI()
    )

    class AdminOnly(backend["viewset_class"]):
        permission_classes = [IsAdminUser]

    router = AdminOnly(
        endpoint="/admin-items",
        model=backend["item_model"],
        response_model=OwnedSchema,
        db_session=backend["session"],
        orm_adapter=backend["adapter"],
    )
    router.register(methods=["LIST"], auth_dependency=auth_dependency)
    app.include_router(router)
    with TestClient(app) as client:
        assert client.get("/admin-items", headers=_headers(1)).status_code == 403
        assert client.get("/admin-items", headers=_headers(3)).status_code == 200


@pytest.fixture
def plain_client(owner_backend):
    backend = owner_backend
    app = (
        _app_with_tortoise_lifespan(backend["adapter"], backend["owned"])
        if backend["name"] == "tortoise"
        else FastAPI()
    )

    class Plain(backend["viewset_class"]):
        pass

    router = Plain(
        endpoint="/plain",
        model=backend["item_model"],
        response_model=OwnedSchema,
        db_session=backend["session"],
        orm_adapter=backend["adapter"],
    )
    router.register(methods=["LIST", "GET", "POST"])
    app.include_router(router)
    with TestClient(app) as client:
        yield client, backend


def test_cross_orm_viewset_without_permissions_unchanged(plain_client):
    client, backend = plain_client
    if backend["name"] == "tortoise":
        created = client.post("/plain", json={"title": "open", "user_id": 1})
        assert created.status_code == 200, created.text
        item_id = created.json()["id"]
    elif backend["name"] == "peewee":
        item = backend["item_model"].create(
            title="open", owner=backend["user_model"].get_by_id(1)
        )
        item_id = item.id
    else:
        db = backend["session"]()
        row = backend["item_model"](title="open", user_id=1)
        db.add(row)
        db.commit()
        item_id = row.id
        db.close()
    assert_plain_viewset_has_no_auth_gate(client, "/plain", item_id)


def test_cross_orm_auto_detect_single_user_fk(owner_backend):
    backend = owner_backend
    init_permissions(user_model=backend["user_model"])

    class Auto(backend["viewset_class"]):
        permission_classes = [IsAuthenticated, IsOwner]

    router = Auto(
        endpoint="/detect",
        model=backend["item_model"],
        response_model=OwnedSchema,
        db_session=backend["session"],
        orm_adapter=backend["adapter"],
    )
    expected = "owner_id" if backend["name"] == "peewee" else "user_id"
    assert router._resolved_owner_field == expected


@pytest.mark.parametrize("factory", ["no_fk", "dual_fk"])
def test_cross_orm_startup_owner_field_errors(owner_backend, factory):
    backend = owner_backend
    init_permissions(user_model=backend["user_model"])

    class OwnerVS(backend["viewset_class"]):
        permission_classes = [IsAuthenticated, IsOwner]

    if factory == "no_fk":
        if backend["name"] == "sqlalchemy":
            from sqlalchemy import Column, Integer, String

            base = backend["adapter"].get_base()

            class Bare(base):
                __tablename__ = "perm_x_bare"
                id = Column(Integer, primary_key=True)
                title = Column(String)
                owner_id = Column(Integer, nullable=False)

            base.metadata.create_all(backend["adapter"].engine)
            model = Bare
        elif backend["name"] == "peewee":
            pw = pytest.importorskip("peewee")
            pw_db = backend["adapter"].database

            class Bare(pw.Model):
                id = pw.AutoField()
                title = pw.TextField()
                owner_id = pw.IntegerField()

                class Meta:
                    database = pw_db
                    table_name = "perm_x_bare"

            pw_db.create_tables([Bare], safe=True)
            model = Bare
        else:
            from tortoise import fields
            from tortoise.models import Model

            class Bare(Model):
                id = fields.IntField(pk=True)
                title = fields.CharField(max_length=50)
                owner_id = fields.IntField()

                class Meta:
                    table = "perm_t_bare"

            model = Bare
        pattern = "no foreign key"
    else:
        if backend["name"] == "sqlalchemy":
            from sqlalchemy import Column, ForeignKey, Integer, String

            base = backend["adapter"].get_base()

            class Dual(base):
                __tablename__ = "perm_x_dual"
                id = Column(Integer, primary_key=True)
                title = Column(String)
                user_id = Column(Integer, ForeignKey("perm_x_accounts.id"), nullable=False)
                editor_id = Column(Integer, ForeignKey("perm_x_accounts.id"), nullable=False)

            base.metadata.create_all(backend["adapter"].engine)
            model = Dual
        elif backend["name"] == "peewee":
            pw = pytest.importorskip("peewee")
            pw_db = backend["adapter"].database

            class Dual(pw.Model):
                id = pw.AutoField()
                title = pw.TextField()
                user = pw.ForeignKeyField(backend["user_model"], backref="dual_a")
                editor = pw.ForeignKeyField(backend["user_model"], backref="dual_b")

                class Meta:
                    database = pw_db
                    table_name = "perm_x_dual"

            pw_db.create_tables([Dual], safe=True)
            model = Dual
        else:
            from tests import permissions_tortoise_models as models

            model = models.PermDualOwnerItem
        pattern = "multiple user foreign keys"

    with pytest.raises(ValueError, match=pattern):
        OwnerVS(
            endpoint="/bad",
            model=model,
            response_model=OwnedSchema,
            db_session=backend["session"],
            orm_adapter=backend["adapter"],
        )


def test_cross_orm_discover_user_foreign_keys(owner_backend):
    backend = owner_backend
    keys = backend["adapter"].discover_user_foreign_keys(
        backend["item_model"], backend["user_model"]
    )
    if backend["name"] == "peewee":
        assert keys == ["owner_id"]
    else:
        assert keys == ["user_id"]


@pytest.fixture
def nested_owner_client(owner_backend):
    backend = owner_backend
    init_permissions(user_model=backend["user_model"])
    doc_ids: Dict[str, int] = {}

    if backend["name"] == "sqlalchemy":
        from sqlalchemy import Column, ForeignKey, Integer, String

        base = backend["adapter"].get_base()

        class Folder(base):
            __tablename__ = "perm_x_folders"
            id = Column(Integer, primary_key=True)
            title = Column(String, nullable=False)

        class Document(base):
            __tablename__ = "perm_x_docs"
            id = Column(Integer, primary_key=True)
            title = Column(String, nullable=False)
            folder_id = Column(Integer, ForeignKey("perm_x_folders.id"), nullable=False)
            user_id = Column(Integer, ForeignKey("perm_x_accounts.id"), nullable=False)

        base.metadata.create_all(backend["adapter"].engine)
        parent_model, child_model = Folder, Document
        db = backend["session"]()
        db.add(Folder(id=1, title="f1"))
        db.add(Document(title="d-user1", folder_id=1, user_id=1))
        db.add(Document(title="d-user2", folder_id=1, user_id=2))
        db.commit()
        for row in db.query(Document).all():
            doc_ids[row.title] = row.id
        db.close()

    elif backend["name"] == "peewee":
        pw = pytest.importorskip("peewee")
        pw_db = backend["adapter"].database

        class Folder(pw.Model):
            id = pw.AutoField()
            title = pw.TextField()

            class Meta:
                database = pw_db
                table_name = "perm_x_folders"

        class Document(pw.Model):
            id = pw.AutoField()
            title = pw.TextField()
            folder = pw.ForeignKeyField(Folder, backref="documents")
            owner = pw.ForeignKeyField(backend["user_model"], backref="documents")

            class Meta:
                database = pw_db
                table_name = "perm_x_docs"

        pw_db.create_tables([Folder, Document], safe=True)
        parent_model, child_model = Folder, Document
        folder = Folder.create(id=1, title="f1")
        doc_ids["d-user1"] = Document.create(
            title="d-user1", folder=folder, owner=backend["user_model"].get_by_id(1)
        ).id
        doc_ids["d-user2"] = Document.create(
            title="d-user2", folder=folder, owner=backend["user_model"].get_by_id(2)
        ).id

    else:
        from tests import permissions_tortoise_models as models

        parent_model, child_model = models.PermFolder, models.PermDocument

        async def seed_nested_docs(perms_models):
            await perms_models.PermFolder.get_or_create(id=1, defaults={"title": "f1"})
            doc1 = await perms_models.PermDocument.create(
                title="d-user1", folder_id=1, user_id=1
            )
            doc2 = await perms_models.PermDocument.create(
                title="d-user2", folder_id=1, user_id=2
            )
            doc_ids["d-user1"] = doc1.id
            doc_ids["d-user2"] = doc2.id

    if backend["name"] == "tortoise":
        app = _app_with_tortoise_lifespan(
            backend["adapter"], backend["owned"], after_seed=seed_nested_docs
        )
    else:
        app = FastAPI()

    folders = backend["viewset_class"](
        endpoint="/folders",
        model=parent_model,
        response_model=FolderSchema,
        db_session=backend["session"],
        orm_adapter=backend["adapter"],
    )
    folders.register()

    class Docs(backend["viewset_class"]):
        permission_classes = [IsAuthenticated, IsOwner]

    docs = Docs(
        endpoint="/folders/{folder_id}/documents",
        model=child_model,
        response_model=DocumentSchema,
        db_session=backend["session"],
        orm_adapter=backend["adapter"],
        nested=NestedConfig(parent_model=parent_model, foreign_key="folder_id"),
    )
    docs.register(methods=["LIST", "GET", "POST"], auth_dependency=auth_dependency)
    app.include_router(folders)
    app.include_router(docs)

    with TestClient(app) as client:
        yield client, doc_ids, backend


def test_cross_orm_nested_documents_respect_owner_scope(nested_owner_client):
    client, docs, backend = nested_owner_client
    headers = _headers(2)
    listed = client.get("/folders/1/documents", headers=headers).json()
    assert {row["title"] for row in listed} == {"d-user2"}
    assert client.get(f"/folders/1/documents/{docs['d-user1']}", headers=headers).status_code == 404
    created = client.post(
        "/folders/1/documents",
        json={"title": "d-new", "user_id": 1},
        headers=headers,
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["folder_id"] == 1
    new_id = body["id"]
    assert client.get(f"/folders/1/documents/{new_id}", headers=headers).status_code == 200
    assert client.get(f"/folders/1/documents/{new_id}", headers=_headers(1)).status_code == 404


def test_cross_orm_soft_delete_restore_scoped(owner_backend):
    backend = owner_backend
    owned = dict(backend["owned"])
    init_permissions(user_model=backend["user_model"])
    app = (
        _app_with_tortoise_lifespan(backend["adapter"], owned)
        if backend["name"] == "tortoise"
        else FastAPI()
    )

    class SoftItems(backend["viewset_class"]):
        permission_classes = [IsAuthenticated, IsOwner]

    router = SoftItems(
        endpoint="/items",
        model=backend["item_model"],
        response_model=OwnedSchema,
        db_session=backend["session"],
        orm_adapter=backend["adapter"],
        soft_delete=SoftDeleteConfig(field="is_deleted"),
    )
    router.register(methods=["DELETE", "RESTORE"], auth_dependency=auth_dependency)
    app.include_router(router)

    with TestClient(app) as client:
        item_id = owned["b1"]
        assert client.delete(f"/items/{item_id}", headers=_headers(1)).status_code == 404
        assert client.delete(f"/items/{item_id}", headers=_headers(2)).status_code == 200
        assert client.post(f"/items/{item_id}/restore", headers=_headers(1)).status_code == 404
        restore = client.post(f"/items/{item_id}/restore", headers=_headers(2))
        assert restore.status_code == 200
