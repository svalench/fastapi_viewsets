"""Тесты DRF-подобных permission_classes."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Header, Request
from fastapi.testclient import TestClient
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String

from fastapi_viewsets import (
    AsyncBaseViewset,
    BasePermission,
    BaseViewset,
    IsAdmin,
    IsAdminUser,
    IsAuthenticated,
    IsOwner,
    SoftDeleteConfig,
    get_user,
    init_permissions,
)
from fastapi_viewsets.db_conf import get_orm_adapter
import fastapi_viewsets.permissions_state as permissions_state
from tests.conftest import TestBase, db_session_factory


class Account(TestBase):
    __tablename__ = "perm_accounts"

    id = Column(Integer, primary_key=True)
    username = Column(String, nullable=False)
    is_staff = Column(Boolean, default=False)


class OwnedItem(TestBase):
    __tablename__ = "perm_owned_items"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("perm_accounts.id"), nullable=False)
    is_deleted = Column(Boolean, default=False)


class DualOwnerItem(TestBase):
    __tablename__ = "perm_dual_owner_items"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("perm_accounts.id"), nullable=False)
    editor_id = Column(Integer, ForeignKey("perm_accounts.id"), nullable=False)


class IntOwnerItem(TestBase):
    __tablename__ = "perm_int_owner_items"

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    owner_id = Column(Integer, nullable=False)


class OwnedItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    title: str
    user_id: Optional[int] = None


USERS = {
    1: SimpleNamespace(id=1, username="alice", is_staff=False),
    2: SimpleNamespace(id=2, username="bob", is_staff=False),
    3: SimpleNamespace(id=3, username="staff", is_staff=True),
    4: SimpleNamespace(id=4, username="admin", is_admin=True),
}


def _request(user=None):
    scope = {
        "type": "http",
        "headers": [],
        "method": "GET",
        "path": "/",
        "http_version": "1.1",
        "query_string": b"",
    }
    request = Request(scope)
    if user is not None:
        request.state.user = user
    return request


def auth_dependency(
    request: Request, x_user_id: Optional[int] = Header(default=None, alias="X-User-Id")
):
    user = USERS.get(x_user_id) if x_user_id is not None else None
    request.state.user = user
    return user


@pytest.fixture
def perm_app(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class ItemsViewset(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    app = FastAPI()
    router = ItemsViewset(
        endpoint="/items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
        tags=["items"],
    )
    router.register(
        methods=["LIST", "GET", "POST", "PUT", "PATCH", "DELETE"],
        auth_dependency=auth_dependency,
    )
    app.include_router(router)
    client = TestClient(app)

    session = db_session_factory()
    try:
        session.add_all(
            [
                Account(id=1, username="alice"),
                Account(id=2, username="bob"),
                Account(id=3, username="staff", is_staff=True),
                OwnedItem(title="a1", user_id=1),
                OwnedItem(title="b1", user_id=2),
            ]
        )
        session.commit()
        owned = {row.title: row.id for row in session.query(OwnedItem).all()}
    finally:
        session.close()

    return client, owned


def test_owner_scoped_crud_and_foreign_id_returns_404(perm_app):
    client, owned = perm_app
    headers = {"X-User-Id": "2"}

    listed = client.get("/items", headers=headers).json()
    assert {row["title"] for row in listed} == {"b1"}

    assert client.get(f"/items/{owned['a1']}", headers=headers).status_code == 404
    assert client.patch(f"/items/{owned['a1']}", json={"title": "hack"}, headers=headers).status_code == 404
    assert client.delete(f"/items/{owned['a1']}", headers=headers).status_code == 404

    created = client.post("/items", json={"title": "new", "user_id": 1}, headers=headers).json()
    assert created["user_id"] == 2
    assert client.get(f"/items/{created['id']}", headers={"X-User-Id": "1"}).status_code == 404


def test_staff_sees_all_rows(perm_app):
    client, owned = perm_app
    headers = {"X-User-Id": "3"}
    titles = {row["title"] for row in client.get("/items", headers=headers).json()}
    assert titles == {"a1", "b1"}
    assert client.get(f"/items/{owned['a1']}", headers=headers).status_code == 200


def test_explicit_owner_field_name(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class ExplicitViewset(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]
        owner_field = "user_id"

    app = FastAPI()
    router = ExplicitViewset(
        endpoint="/items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    router.register(methods=["LIST"], auth_dependency=auth_dependency)
    app.include_router(router)

    session = db_session_factory()
    session.add_all([Account(id=1, username="alice"), OwnedItem(title="x", user_id=1)])
    session.commit()
    session.close()

    client = TestClient(app)
    assert len(client.get("/items", headers={"X-User-Id": "1"}).json()) == 1


def test_auto_detect_single_user_fk(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class AutoViewset(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    router = AutoViewset(
        endpoint="/items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    assert router._resolved_owner_field == "user_id"


def test_startup_errors_for_ambiguous_or_missing_owner_fk(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class IntViewset(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    with pytest.raises(ValueError, match="no foreign key"):
        IntViewset(
            endpoint="/x",
            model=IntOwnerItem,
            response_model=OwnedItemSchema,
            db_session=db_session_factory,
        )

    class DualViewset(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    with pytest.raises(ValueError, match="multiple user foreign keys"):
        DualViewset(
            endpoint="/x",
            model=DualOwnerItem,
            response_model=OwnedItemSchema,
            db_session=db_session_factory,
        )


def test_unauthenticated_is_forbidden(perm_app):
    client, _ = perm_app
    assert client.get("/items").status_code == 403


def test_viewset_without_permissions_unchanged(test_engine, db_session_factory, test_app):
    class PlainViewset(BaseViewset):
        pass

    router = PlainViewset(
        endpoint="/plain",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    router.register(methods=["LIST", "GET", "POST"])
    test_app.include_router(router)
    client = TestClient(test_app)

    session = db_session_factory()
    row = OwnedItem(title="open", user_id=1)
    session.add(row)
    session.commit()
    item_id = row.id
    session.close()

    assert client.get("/plain").status_code == 200
    assert client.get(f"/plain/{item_id}").status_code == 200
    assert client.post("/plain", json={"title": "n", "user_id": 9}).status_code == 200


def test_permissions_with_soft_delete(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class SoftViewset(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    app = FastAPI()
    router = SoftViewset(
        endpoint="/items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
        soft_delete=SoftDeleteConfig(field="is_deleted"),
    )
    router.register(methods=["DELETE", "RESTORE"], auth_dependency=auth_dependency)
    app.include_router(router)
    client = TestClient(app)

    session = db_session_factory()
    session.add_all([Account(id=1, username="alice"), OwnedItem(title="x", user_id=1)])
    session.commit()
    item_id = session.query(OwnedItem).first().id
    session.close()

    headers = {"X-User-Id": "2"}
    assert client.delete(f"/items/{item_id}", headers=headers).status_code == 404

    headers = {"X-User-Id": "1"}
    assert client.delete(f"/items/{item_id}", headers=headers).status_code == 200
    assert client.post(f"/items/{item_id}/restore", headers=headers).status_code == 200


def test_base_permission_defaults():
    permission = BasePermission()
    request = _request()
    assert permission.has_permission(request, None, "GET") is True
    assert permission.has_object_permission(request, None, "GET", object()) is True
    assert permission.get_scope(request, None) == {}
    assert permission.filter_queryset(request, None, "qs") == "qs"


def test_get_user_and_is_admin_alias():
    request = _request(USERS[1])
    assert get_user(request) is USERS[1]
    assert IsAdmin is IsAdminUser


def test_is_owner_field_on_permission_class(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class OwnerOnClass(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner(field="user_id")]

    router = OwnerOnClass(
        endpoint="/items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    assert router._resolved_owner_field == "user_id"


def test_is_authenticated_only_skips_owner_resolution(test_engine, db_session_factory):
    class AuthOnly(BaseViewset):
        permission_classes = [IsAuthenticated]

    router = AuthOnly(
        endpoint="/items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    assert router._resolved_owner_field is None
    assert router.uses_permissions()


def test_init_permissions_required_for_auto_detect(test_engine, db_session_factory):
    previous = permissions_state.get_user_model()
    permissions_state.set_user_model(None)
    try:

        class AutoViewset(BaseViewset):
            permission_classes = [IsAuthenticated, IsOwner]

        with pytest.raises(ValueError, match="init_permissions"):
            AutoViewset(
                endpoint="/x",
                model=OwnedItem,
                response_model=OwnedItemSchema,
                db_session=db_session_factory,
            )
    finally:
        permissions_state.set_user_model(previous)


def test_owner_permissions_require_model(db_session_factory):
    init_permissions(user_model=Account)

    class OwnerViewset(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    with pytest.raises(ValueError, match="require a model"):
        OwnerViewset(
            endpoint="/x",
            model=None,
            response_model=OwnedItemSchema,
            db_session=db_session_factory,
        )


def test_discover_user_foreign_keys_on_adapter():
    init_permissions(user_model=Account)
    adapter = get_orm_adapter()
    assert adapter.discover_user_foreign_keys(OwnedItem, Account) == ["user_id"]
    assert adapter.discover_user_foreign_keys(DualOwnerItem, Account) == ["user_id", "editor_id"]


def test_admin_only_viewset(test_engine, db_session_factory):
    class AdminViewset(BaseViewset):
        permission_classes = [IsAdminUser]

    app = FastAPI()
    router = AdminViewset(
        endpoint="/admin-items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    router.register(methods=["LIST"], auth_dependency=auth_dependency)
    app.include_router(router)
    client = TestClient(app)

    session = db_session_factory()
    session.add(OwnedItem(title="secret", user_id=1))
    session.commit()
    session.close()

    assert client.get("/admin-items", headers={"X-User-Id": "1"}).status_code == 403
    assert client.get("/admin-items", headers={"X-User-Id": "3"}).status_code == 200
    assert client.get("/admin-items", headers={"X-User-Id": "4"}).status_code == 200


def test_custom_object_permission_returns_403(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class DenyObject(BasePermission):
        def has_object_permission(self, request, view, action, obj):
            return False

    class LockedViewset(BaseViewset):
        permission_classes = [IsAuthenticated, DenyObject]

    app = FastAPI()
    router = LockedViewset(
        endpoint="/locked",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    router.register(methods=["GET"], auth_dependency=auth_dependency)
    app.include_router(router)
    client = TestClient(app)

    session = db_session_factory()
    session.add(OwnedItem(title="x", user_id=1))
    session.commit()
    item_id = session.query(OwnedItem).first().id
    session.close()

    assert client.get(f"/locked/{item_id}", headers={"X-User-Id": "1"}).status_code == 403


def test_put_with_owner_permissions(perm_app):
    client, owned = perm_app
    headers = {"X-User-Id": "2"}
    item_id = owned["b1"]
    response = client.put(f"/items/{item_id}", json={"title": "updated", "user_id": 99}, headers=headers)
    assert response.status_code == 200
    assert response.json()["title"] == "updated"
    assert response.json()["user_id"] == 2


def test_permission_body_model_cache_and_programmatic_list(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class ItemsViewset(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    router = ItemsViewset(
        endpoint="/items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    router.register(methods=["POST"], auth_dependency=auth_dependency)
    router.register(methods=["POST"], auth_dependency=auth_dependency)
    first = router._permission_body_model(OwnedItemSchema)
    second = router._permission_body_model(OwnedItemSchema)
    assert first is second


def test_async_viewset_permission_scope(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class AsyncItems(AsyncBaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    viewset = AsyncItems(
        endpoint="/async-items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    scope = viewset._permission_scope(_request(USERS[2]))
    assert scope == {"user_id": 2}


@pytest.mark.asyncio
async def test_async_viewset_permission_handlers(db_session_factory, monkeypatch):
    init_permissions(user_model=Account)

    class AsyncItems(AsyncBaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    viewset = AsyncItems(
        endpoint="/async-items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    request = _request(USERS[2])
    row = OwnedItem(id=1, title="async", user_id=2)

    async def list_rows(*args, **kwargs):
        return [row]

    async def load_row(*args, **kwargs):
        return row

    async def write_row(*args, **kwargs):
        return row

    async def delete_row(*args, **kwargs):
        return True

    monkeypatch.setattr("fastapi_viewsets.async_base.get_list_queryset", list_rows)
    monkeypatch.setattr("fastapi_viewsets.async_base.get_element_by_id", load_row)
    monkeypatch.setattr("fastapi_viewsets.async_base.create_element", write_row)
    monkeypatch.setattr("fastapi_viewsets.async_base.update_element", write_row)
    monkeypatch.setattr("fastapi_viewsets.async_base.delete_element", delete_row)

    assert await viewset.list(request=request) == [row]
    assert await viewset.get_element(1, request=request) is row
    assert await viewset.create_element(OwnedItemSchema(title="async"), request=request) is row
    assert await viewset.update_element(1, OwnedItemSchema(title="async"), request=request) is row
    assert await viewset.delete_element(1, request=request)["status"] is True


def test_is_owner_scope_uses_pk_attribute():
    permission = IsOwner()
    view = SimpleNamespace(_resolved_owner_field="user_id")
    request = _request(SimpleNamespace(pk=9))
    assert permission.get_scope(request, view) == {"user_id": 9}


def test_is_owner_scope_empty_when_user_has_no_pk():
    permission = IsOwner()
    view = SimpleNamespace(_resolved_owner_field="user_id")
    request = _request(SimpleNamespace())
    assert permission.get_scope(request, view) == {}


def test_is_owner_requires_resolved_owner_field():
    permission = IsOwner()
    with pytest.raises(RuntimeError, match="owner_field"):
        permission._owner_field(SimpleNamespace())


def test_permission_body_model_noop_without_owner_field(test_engine, db_session_factory):
    router = BaseViewset(
        endpoint="/noop",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    assert router._permission_body_model(OwnedItemSchema) is OwnedItemSchema


def test_permission_strip_owner_validator_skips_non_dict(test_engine, db_session_factory):
    init_permissions(user_model=Account)

    class ItemsViewset(BaseViewset):
        permission_classes = [IsAuthenticated, IsOwner]

    router = ItemsViewset(
        endpoint="/items",
        model=OwnedItem,
        response_model=OwnedItemSchema,
        db_session=db_session_factory,
    )
    patched = router._permission_body_model(OwnedItemSchema)
    row = OwnedItem(title="from-orm", user_id=99)
    validated = patched.model_validate(row, from_attributes=True)
    assert validated.title == "from-orm"
