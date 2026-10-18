"""Regression coverage for database defaults and validation errors."""
import pytest
from fastapi import HTTPException


@pytest.fixture
def sqlalchemy_model(tmp_path):
    from sqlalchemy import Column, Integer, String, text

    from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
    adapter = SQLAlchemyAdapter(database_url=f"sqlite:///{tmp_path}/defaults.db")
    base = adapter.get_base()
    class Item(base):
        __tablename__ = "defaults"
        id = Column(Integer, primary_key=True)
        name = Column(String, nullable=False)
        client_default = Column(Integer, nullable=False, default=7)
        server_default = Column(Integer, nullable=False, server_default=text("9"))
    base.metadata.create_all(adapter.engine)
    yield adapter, Item
    adapter.engine.dispose()


def test_sqlalchemy_create_honors_defaults(sqlalchemy_model):
    adapter, model = sqlalchemy_model
    item = adapter.create_element(model, adapter.get_session, {"name": "test"})
    assert (item.client_default, item.server_default) == (7, 9)


@pytest.mark.asyncio
async def test_sqlalchemy_async_create_honors_defaults(sqlalchemy_model):
    adapter, model = sqlalchemy_model
    try:
        item = await adapter.create_element_async(model, adapter.get_async_session, {"name": "test"})
        assert (item.client_default, item.server_default) == (7, 9)
        with pytest.raises(HTTPException, match="Missing required fields"):
            await adapter.create_element_async(model, adapter.get_async_session, {})
    finally:
        await adapter.async_engine.dispose()


def test_peewee_create_honors_defaults_and_validation(tmp_path):
    peewee = pytest.importorskip("peewee")
    from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
    adapter = PeeweeAdapter(database_url=f"sqlite:///{tmp_path}/peewee.db")
    class Item(peewee.Model):
        name = peewee.CharField()
        count = peewee.IntegerField(default=7)
        class Meta:
            database = adapter.database
    Item.create_table()
    try:
        item = adapter.create_element(Item, adapter.get_session, {"name": "test"})
        assert item.count == 7
        with pytest.raises(HTTPException, match="Missing required fields"):
            adapter.create_element(Item, adapter.get_session, {})
    finally:
        adapter.database.close()


def test_peewee_update_constraint_returns_safe_conflict(tmp_path):
    peewee = pytest.importorskip("peewee")
    from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter
    adapter = PeeweeAdapter(database_url=f"sqlite:///{tmp_path}/unique.db")
    class Item(peewee.Model):
        name = peewee.CharField(unique=True)
        class Meta:
            database = adapter.database
    Item.create_table()
    try:
        Item.create(name="private-first")
        other = Item.create(name="private-second")
        with pytest.raises(HTTPException) as error:
            adapter.update_element(Item, adapter.get_session, other.id, {"name": "private-first"}, True)
        assert error.value.status_code == 409
        assert "private-first" not in error.value.detail
        assert Item.get_by_id(other.id).name == "private-second"
    finally:
        adapter.database.close()


@pytest.mark.asyncio
async def test_tortoise_update_constraint_and_create_validation(tmp_path):
    pytest.importorskip("tortoise")
    from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
    from tests.tortoise_models import UniqueNameTortoiseModel as Item
    adapter = TortoiseAdapter(database_url=f"sqlite://{tmp_path}/unique.db",
                              models=["tests.tortoise_models"])
    await adapter.initialize(generate_schemas=True)
    try:
        await Item.create(name="private-first")
        other = await Item.create(name="private-second")
        with pytest.raises(HTTPException) as error:
            await adapter.update_element_async(Item, adapter.get_async_session, other.id,
                                               {"name": "private-first"}, True)
        assert error.value.status_code == 409
        assert "private-first" not in error.value.detail
        assert (await Item.get(id=other.id)).name == "private-second"
        with pytest.raises(HTTPException, match="Missing required fields"):
            await adapter.create_element_async(Item, adapter.get_async_session, {})
    finally:
        await adapter.close()
