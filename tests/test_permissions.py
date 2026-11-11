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
    BaseViewset,
    IsAuthenticated,
    IsOwner,
    SoftDeleteConfig,
    init_permissions,
)
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
}


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
    router.register(methods=["LIST", "GET", "POST", "PATCH", "DELETE"], auth_dependency=auth_dependency)
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
