"""Tests for server-side search, ordering and filtering (v1.5.0).

Covers:
* ``ListConfig`` extraction from Pydantic schemas
* ``parse_ordering_param`` / ``parse_filters`` parsing helpers
* ``BaseViewset.list`` and ``AsyncBaseViewset.list`` end-to-end with
  search, ordering and filter query params (SQLAlchemy)
* Adapter-level search/ordering/filter behaviour for Tortoise and
  Peewee (skipped when the extra is not installed)
"""

import os

# ---------------------------------------------------------------------------
# Fixtures: SQLAlchemy adapter with a dedicated table for these tests
# ---------------------------------------------------------------------------
import tempfile
from typing import Optional

import pytest
from pydantic import BaseModel, ConfigDict

from fastapi_viewsets import AsyncBaseViewset, BaseViewset
from fastapi_viewsets.filtering import (
    coerce_value,
    get_list_config,
    parse_filters,
    parse_ordering_param,
)
from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter

_fdb_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
_fdb_path = _fdb_file.name
_fdb_file.close()

FILTER_DB_URL = f"sqlite:///{_fdb_path}"
FILTER_ASYNC_DB_URL = f"sqlite+aiosqlite:///{_fdb_path}"


@pytest.fixture()
def filter_adapter():
    adapter = SQLAlchemyAdapter(
        database_url=FILTER_DB_URL,
        async_database_url=FILTER_ASYNC_DB_URL,
    )
    Base = adapter.get_base()
    from sqlalchemy import Column, Integer, String

    class FUser(Base):
        __tablename__ = "f_user_search"
        id = Column(Integer, primary_key=True)
        username = Column(String, nullable=False)
        email = Column(String, nullable=False)
        status = Column(String, nullable=True)
        age = Column(Integer, nullable=True)

    Base.metadata.create_all(adapter.engine)

    rows = [
        {"username": "Alice", "email": "alice@example.com", "status": "active", "age": 30},
        {"username": "Bob", "email": "bob@example.com", "status": "inactive", "age": 20},
        {"username": "Carol", "email": "carol@example.com", "status": "active", "age": 40},
    ]
    from sqlalchemy import insert
    with adapter.engine.connect() as conn:
        conn.execute(insert(FUser), rows)
        conn.commit()

    yield adapter, FUser

    Base.metadata.drop_all(adapter.engine)
    adapter.engine.dispose()
    try:
        os.unlink(_fdb_path)
    except FileNotFoundError:
        pass


class FUserSchema(BaseModel):
    """Schema with declarative ListConfig."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    status: Optional[str] = None
    age: Optional[int] = None

    class ListConfig:
        search_fields = ["username", "email"]
        ordering_fields = ["username", "age"]
        ordering = ["username"]
        filters = ["status", "age", "username"]


# ---------------------------------------------------------------------------
# Unit tests: config extraction and parsing helpers
# ---------------------------------------------------------------------------


class TestFilteringHelpers:
    def test_get_list_config_none(self):
        config = get_list_config(None)
        assert config.search_fields == []
        assert config.ordering == []
        assert config.filters == []

    def test_get_list_config_missing(self):
        class Plain(BaseModel):
            x: int
        config = get_list_config(Plain)
        assert config.search_fields == []

    def test_get_list_config_present(self):
        config = get_list_config(FUserSchema)
        assert config.search_fields == ["username", "email"]
        assert config.ordering == ["username"]
        assert "status" in config.filters

    def test_coerce_value(self):
        assert coerce_value("42") == 42
        assert coerce_value("3.5") == 3.5
        assert coerce_value("true") is True
        assert coerce_value("false") is False
        assert coerce_value("hello") == "hello"
        assert coerce_value(None) is None

    def test_parse_ordering_param_empty_uses_default(self):
        assert parse_ordering_param(None, ["a"], ["-a"]) == ["-a"]
        assert parse_ordering_param("", ["a"], ["-a"]) == ["-a"]
        assert parse_ordering_param(None, ["a"]) is None

    def test_parse_ordering_param_valid(self):
        assert parse_ordering_param("-name,age", ["name", "age"]) == ["-name", "age"]

    def test_parse_ordering_param_invalid_field(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            parse_ordering_param("hacker_field", ["name"])
        assert exc.value.status_code == 400

    def test_parse_ordering_param_no_whitelist_ignores_param(self):
        # Without ordering_fields the query parameter is ignored entirely
        assert parse_ordering_param("anything") is None
        assert parse_ordering_param("anything", [], ["-a"]) == ["-a"]

    def test_parse_filters_whitelist(self):
        params = {"status": "active", "age__gte": "25", "limit": "5", "evil": "1"}
        filters = parse_filters(params, ["status", "age"])
        assert filters["status"] == ("eq", "active")
        assert filters["age"] == ("gte", 25)
        assert "evil" not in filters
        assert "limit" not in filters

    def test_parse_filters_in_operator(self):
        filters = parse_filters({"status__in": "active,pending"}, ["status"])
        assert filters["status"] == ("in", ["active", "pending"])

    def test_parse_filters_empty_value_ignored(self):
        filters = parse_filters({"status": ""}, ["status"])
        assert filters == {}

    def test_parse_filters_no_allowed_fields(self):
        assert parse_filters({"status": "active"}, []) == {}


# ---------------------------------------------------------------------------
# Sync viewset end-to-end
# ---------------------------------------------------------------------------


class TestSyncViewsetList:
    @pytest.fixture()
    def client(self, filter_adapter):
        adapter, model = filter_adapter

        class VS(BaseViewset):
            pass

        vs = VS(
            endpoint="/fusers",
            model=model,
            db_session=adapter.get_session,
            response_model=FUserSchema,
            orm_adapter=adapter,
        )
        vs.register()
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(vs)
        return TestClient(app)

    def _usernames(self, response):
        return [u["username"] for u in response.json()]

    def test_plain_list_uses_default_ordering(self, client):
        data = client.get("/fusers").json()
        assert [u["username"] for u in data] == ["Alice", "Bob", "Carol"]

    def test_search_is_case_insensitive(self, client):
        data = client.get("/fusers", params={"search": "ALI"}).json()
        assert [u["username"] for u in data] == ["Alice"]

    def test_search_across_fields(self, client):
        data = client.get("/fusers", params={"search": "example"}).json()
        assert len(data) == 3

    def test_ordering_desc(self, client):
        data = client.get("/fusers", params={"ordering": "-age"}).json()
        assert [u["username"] for u in data] == ["Carol", "Alice", "Bob"]

    def test_ordering_invalid_returns_400(self, client):
        response = client.get("/fusers", params={"ordering": "email"})
        assert response.status_code == 400

    def test_filter_exact(self, client):
        data = client.get("/fusers", params={"status": "active"}).json()
        assert [u["username"] for u in data] == ["Alice", "Carol"]

    def test_filter_gte(self, client):
        data = client.get("/fusers", params={"age__gte": 30}).json()
        assert [u["username"] for u in data] == ["Alice", "Carol"]

    def test_filter_lte(self, client):
        data = client.get("/fusers", params={"age__lte": 20}).json()
        assert [u["username"] for u in data] == ["Bob"]

    def test_filter_ne(self, client):
        data = client.get("/fusers", params={"status__ne": "active"}).json()
        assert [u["username"] for u in data] == ["Bob"]

    def test_filter_in(self, client):
        data = client.get("/fusers", params={"age__in": "20,40"}).json()
        assert [u["username"] for u in data] == ["Bob", "Carol"]

    def test_filter_contains(self, client):
        data = client.get("/fusers", params={"username__contains": "li"}).json()
        assert [u["username"] for u in data] == ["Alice"]

    def test_unknown_filter_ignored(self, client):
        data = client.get("/fusers", params={"hax": "1"}).json()
        assert len(data) == 3

    def test_combined_search_filter_ordering_pagination(self, client):
        data = client.get(
            "/fusers",
            params={"search": "example", "status": "active", "ordering": "-age", "limit": 1},
        ).json()
        assert [u["username"] for u in data] == ["Carol"]

    def test_backward_compat_no_list_config(self, filter_adapter):
        """A schema without ListConfig ignores search/ordering/filter params."""
        adapter, model = filter_adapter

        class PlainSchema(BaseModel):
            model_config = ConfigDict(from_attributes=True)
            id: int
            username: str

        class VS(BaseViewset):
            pass

        vs = VS(
            endpoint="/plain",
            model=model,
            db_session=adapter.get_session,
            response_model=PlainSchema,
            orm_adapter=adapter,
        )
        vs.register()
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(vs)
        client = TestClient(app)

        data = client.get(
            "/plain", params={"search": "ali", "ordering": "evil", "status": "x"}
        ).json()
        assert len(data) == 3


# ---------------------------------------------------------------------------
# Async viewset end-to-end
# ---------------------------------------------------------------------------


class TestAsyncViewsetList:
    @pytest.fixture()
    def client(self, filter_adapter):
        adapter, model = filter_adapter

        class VS(AsyncBaseViewset):
            pass

        vs = VS(
            endpoint="/fusers",
            model=model,
            db_session=adapter.get_async_session,
            response_model=FUserSchema,
            orm_adapter=adapter,
        )
        vs.register()
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        app = FastAPI()
        app.include_router(vs)
        return TestClient(app)

    def test_async_search(self, client):
        data = client.get("/fusers", params={"search": "carol"}).json()
        assert [u["username"] for u in data] == ["Carol"]

    def test_async_ordering_default(self, client):
        data = client.get("/fusers").json()
        assert [u["username"] for u in data] == ["Alice", "Bob", "Carol"]

    def test_async_filter_and_ordering(self, client):
        data = client.get(
            "/fusers", params={"status": "active", "ordering": "-age"}
        ).json()
        assert [u["username"] for u in data] == ["Carol", "Alice"]


# ---------------------------------------------------------------------------
# Tortoise adapter (skipped without the extra)
# ---------------------------------------------------------------------------


class TestTortoiseSearchOrdering:
    @pytest.mark.asyncio
    async def test_tortoise_search_ordering_filters(self):
        try:
            from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
            from tests.tortoise_models import SimpleTortoiseModel
        except ImportError:
            pytest.skip("Tortoise ORM not available")

        adapter = TortoiseAdapter(
            database_url="sqlite://:memory:",
            models=["tests.tortoise_models"],
            app_label="test",
        )
        from tortoise import Tortoise

        await adapter._ensure_initialized()
        await Tortoise.generate_schemas(safe=True)
        try:
            await SimpleTortoiseModel.create(name="Apple", value=10)
            await SimpleTortoiseModel.create(name="banana", value=20)
            await SimpleTortoiseModel.create(name="Cherry", value=30)

            # search (case-insensitive)
            result = await adapter.get_list_queryset_async(
                SimpleTortoiseModel,
                adapter.get_async_session,
                search="AN",
                search_fields=["name"],
            )
            assert [r.name for r in result] == ["banana"]

            # ordering desc + filter gte
            result = await adapter.get_list_queryset_async(
                SimpleTortoiseModel,
                adapter.get_async_session,
                ordering=["-value"],
                filters={"value": ("gte", 20)},
            )
            assert [r.value for r in result] == [30, 20]

            # in operator
            result = await adapter.get_list_queryset_async(
                SimpleTortoiseModel,
                adapter.get_async_session,
                filters={"value": ("in", [10, 30])},
                ordering=["value"],
            )
            assert [r.value for r in result] == [10, 30]
        finally:
            await Tortoise.close_connections()


# ---------------------------------------------------------------------------
# Peewee adapter (skipped without the extra)
# ---------------------------------------------------------------------------


class TestPeeweeSearchOrdering:
    def test_peewee_search_ordering_filters(self):
        try:
            from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter

            adapter = PeeweeAdapter(database_url=FILTER_DB_URL)
        except ImportError:
            pytest.skip("Peewee not available")

        Base = adapter.get_base()
        from peewee import CharField, IntegerField

        class PUser(Base):
            username = CharField()
            status = CharField(default="active")
            age = IntegerField(null=True)

        PUser._meta.database = adapter.database
        PUser.create_table()
        try:
            PUser.create(username="Alpha", status="active", age=30)
            PUser.create(username="beta", status="inactive", age=20)
            PUser.create(username="Gamma", status="active", age=40)

            # search (case-insensitive)
            result = adapter.get_list_queryset(
                PUser, adapter.get_session, search="AM", search_fields=["username"]
            )
            assert [u.username for u in result] == ["Gamma"]

            # ordering desc + filter
            result = adapter.get_list_queryset(
                PUser,
                adapter.get_session,
                ordering=["-age"],
                filters={"status": ("eq", "active")},
            )
            assert [u.username for u in result] == ["Gamma", "Alpha"]

            # ne operator
            result = adapter.get_list_queryset(
                PUser,
                adapter.get_session,
                filters={"status": ("ne", "active")},
                ordering=["username"],
            )
            assert [u.username for u in result] == ["beta"]
        finally:
            PUser.drop_table()
