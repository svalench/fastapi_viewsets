"""Tests for select_related / prefetch_related support via RelatedConfig."""

import pytest
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import asyncio

from fastapi_viewsets.serializer_utils import get_select_related, get_prefetch_related
from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter
from fastapi_viewsets.utils import get_list_queryset, get_element_by_id
from fastapi_viewsets.async_utils import get_list_queryset as async_get_list_queryset
from fastapi_viewsets.async_utils import get_element_by_id as async_get_element_by_id


# ---------------------------------------------------------------------------
# Pydantic schemas for serializer_utils tests
# ---------------------------------------------------------------------------

class PlainSchema(BaseModel):
    id: int
    name: str


class RelatedSchema(BaseModel):
    id: int
    name: str

    class RelatedConfig:
        select_related = ["author"]
        prefetch_related = ["tags"]


class PartialSchema(BaseModel):
    id: int

    class RelatedConfig:
        select_related = ["category"]


# ---------------------------------------------------------------------------
# serializer_utils tests
# ---------------------------------------------------------------------------

class TestSerializerUtils:
    def test_plain_schema_returns_empty_lists(self):
        assert get_select_related(PlainSchema) == []
        assert get_prefetch_related(PlainSchema) == []

    def test_related_schema_reads_both(self):
        assert get_select_related(RelatedSchema) == ["author"]
        assert get_prefetch_related(RelatedSchema) == ["tags"]

    def test_partial_schema_missing_prefetch(self):
        assert get_select_related(PartialSchema) == ["category"]
        assert get_prefetch_related(PartialSchema) == []


# ---------------------------------------------------------------------------
# SQLAlchemy models with relationships (local base to avoid conftest clashes)
# ---------------------------------------------------------------------------

LocalBase = declarative_base()


class Author(LocalBase):
    __tablename__ = "test_author"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    posts = relationship("Post", back_populates="author")


class Post(LocalBase):
    __tablename__ = "test_post"
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    author_id = Column(Integer, ForeignKey("test_author.id"))
    author = relationship("Author", back_populates="posts")


# ---------------------------------------------------------------------------
# Sync SQLAlchemy adapter tests
# ---------------------------------------------------------------------------

class TestSQLAlchemySyncSelectRelated:
    @pytest.fixture(scope="function")
    def sync_adapter(self):
        engine = create_engine("sqlite:///:memory:")
        LocalBase.metadata.create_all(engine)
        adapter = SQLAlchemyAdapter(
            database_url="sqlite:///:memory:",
            engine=engine,
            base=LocalBase,
        )
        yield adapter
        engine.dispose()

    @pytest.fixture(scope="function")
    def db_factory(self, sync_adapter):
        return sync_adapter.get_session

    def test_get_list_with_select_related(self, sync_adapter, db_factory):
        db = db_factory()
        author = Author(name="Alice")
        db.add(author)
        db.add(Post(title="Hello", author=author))
        db.commit()
        db.close()

        posts = sync_adapter.get_list_queryset(
            Post, db_factory, select_related=["author"]
        )
        assert len(posts) == 1
        assert posts[0].author.name == "Alice"

    def test_get_element_with_select_related(self, sync_adapter, db_factory):
        db = db_factory()
        author = Author(name="Bob")
        db.add(author)
        post = Post(title="World", author=author)
        db.add(post)
        db.commit()
        post_id = post.id
        db.close()

        result = sync_adapter.get_element_by_id(
            Post, db_factory, post_id, select_related=["author"]
        )
        assert result.author.name == "Bob"


# ---------------------------------------------------------------------------
# Async SQLAlchemy adapter tests
# ---------------------------------------------------------------------------

class TestSQLAlchemyAsyncSelectRelated:
    @pytest.fixture(scope="function")
    async def async_adapter(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(LocalBase.metadata.create_all)
        adapter = SQLAlchemyAdapter(
            database_url="sqlite:///:memory:",
            async_engine=engine,
            base=LocalBase,
        )
        yield adapter
        await engine.dispose()

    @pytest.fixture(scope="function")
    def async_db_factory(self, async_adapter):
        return async_adapter.get_async_session

    @pytest.mark.asyncio
    async def test_get_list_async_with_select_related(self, async_adapter, async_db_factory):
        db = async_db_factory()
        async with db:
            author = Author(name="Alice")
            db.add(author)
            db.add(Post(title="Hello", author=author))
            await db.commit()

        posts = await async_adapter.get_list_queryset_async(
            Post, async_db_factory, select_related=["author"]
        )
        assert len(posts) == 1
        assert posts[0].author.name == "Alice"

    @pytest.mark.asyncio
    async def test_get_element_async_with_select_related(self, async_adapter, async_db_factory):
        db = async_db_factory()
        async with db:
            author = Author(name="Bob")
            db.add(author)
            post = Post(title="World", author=author)
            db.add(post)
            await db.commit()
            post_id = post.id

        result = await async_adapter.get_element_by_id_async(
            Post, async_db_factory, post_id, select_related=["author"]
        )
        assert result.author.name == "Bob"


# ---------------------------------------------------------------------------
# Utils / AsyncUtils integration with response_model + RelatedConfig
# ---------------------------------------------------------------------------

class PostSchema(BaseModel):
    id: int
    title: str

    model_config = ConfigDict(from_attributes=True)

    class RelatedConfig:
        select_related = ["author"]


class TestUtilsWithRelatedConfig:
    @pytest.fixture(scope="function")
    def sync_adapter(self):
        engine = create_engine("sqlite:///:memory:")
        LocalBase.metadata.create_all(engine)
        adapter = SQLAlchemyAdapter(
            database_url="sqlite:///:memory:",
            engine=engine,
            base=LocalBase,
        )
        yield adapter
        engine.dispose()

    @pytest.fixture(scope="function")
    def db_factory(self, sync_adapter):
        return sync_adapter.get_session

    def test_sync_utils_infer_select_related_from_schema(self, sync_adapter, db_factory):
        db = db_factory()
        author = Author(name="Charlie")
        db.add(author)
        db.add(Post(title="Sync", author=author))
        db.commit()
        db.close()

        posts = get_list_queryset(
            Post,
            db_factory,
            orm_adapter=sync_adapter,
            response_model=PostSchema,
        )
        assert len(posts) == 1
        assert posts[0].author.name == "Charlie"

    def test_sync_utils_explicit_override_schema(self, sync_adapter, db_factory):
        db = db_factory()
        author = Author(name="Delta")
        db.add(author)
        post = Post(title="Override", author=author)
        db.add(post)
        db.commit()
        post_id = post.id
        db.close()

        # pass explicit empty select_related to override schema
        result = get_element_by_id(
            Post,
            db_factory,
            post_id,
            orm_adapter=sync_adapter,
            response_model=PostSchema,
            select_related=[],
        )
        # author is NOT eagerly loaded, but object is still returned
        assert result.id == post_id


class TestAsyncUtilsWithRelatedConfig:
    @pytest.fixture(scope="function")
    async def async_adapter(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(LocalBase.metadata.create_all)
        adapter = SQLAlchemyAdapter(
            database_url="sqlite:///:memory:",
            async_engine=engine,
            base=LocalBase,
        )
        yield adapter
        await engine.dispose()

    @pytest.fixture(scope="function")
    def async_db_factory(self, async_adapter):
        return async_adapter.get_async_session

    @pytest.mark.asyncio
    async def test_async_utils_infer_select_related_from_schema(self, async_adapter, async_db_factory):
        db = async_db_factory()
        async with db:
            author = Author(name="Eve")
            db.add(author)
            db.add(Post(title="Async", author=author))
            await db.commit()

        posts = await async_get_list_queryset(
            Post,
            async_db_factory,
            orm_adapter=async_adapter,
            response_model=PostSchema,
        )
        assert len(posts) == 1
        assert posts[0].author.name == "Eve"

    @pytest.mark.asyncio
    async def test_async_utils_explicit_override_schema(self, async_adapter, async_db_factory):
        db = async_db_factory()
        async with db:
            author = Author(name="Frank")
            db.add(author)
            post = Post(title="OverrideAsync", author=author)
            db.add(post)
            await db.commit()
            post_id = post.id

        result = await async_get_element_by_id(
            Post,
            async_db_factory,
            post_id,
            orm_adapter=async_adapter,
            response_model=PostSchema,
            select_related=[],
        )
        assert result.id == post_id
