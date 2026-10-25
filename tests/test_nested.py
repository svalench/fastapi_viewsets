"""Nested resources with real foreign keys across all supported ORM modes."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

import pytest
from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from fastapi.testclient import TestClient
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, create_model, model_validator

from fastapi_viewsets import AsyncBaseViewset, BaseViewset, NestedConfig, SoftDeleteConfig


class PostSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = None
    title: str
    is_deleted: bool = False


class CommentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")
    id: Optional[int] = None
    post_id: int = Field(alias="postId", gt=0)
    text: str = Field(min_length=2)
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_bound_parent(self):
        if self.post_id is None or self.post_id <= 0:
            raise ValueError("parent must be bound before full-model validation")
        return self

    class ListConfig:
        search_fields = ["text"]
        ordering_fields = ["id", "text"]
        ordering = ["id"]
        filters = ["post_id", "text", "is_deleted"]


@pytest.fixture(params=["sqlalchemy", "sqlalchemy-async", "peewee", "tortoise"])
def backend(request, tmp_path):
    name, id_kind = request.param if isinstance(request.param, tuple) else (request.param, "int")
    path = tmp_path / "nested.db"
    if name.startswith("sqlalchemy"):
        from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Uuid

        from fastapi_viewsets.orm.sqlalchemy_adapter import SQLAlchemyAdapter

        adapter = SQLAlchemyAdapter(database_url=f"sqlite:///{path}")
        base = adapter.get_base()

        class Post(base):
            __tablename__ = "nested_posts"
            id = (
                Column(Integer, primary_key=True)
                if id_kind == "int"
                else Column(Uuid, primary_key=True, default=uuid4)
                if id_kind == "uuid"
                else Column(String, primary_key=True, default=lambda: uuid4().hex)
            )
            title = Column(String, nullable=False)
            is_deleted = Column(Boolean, nullable=False, default=False)

        class Comment(base):
            __tablename__ = "nested_comments"
            id = Column(Integer, primary_key=True)
            post_id = Column(
                "post_ref",
                Integer if id_kind == "int" else Uuid if id_kind == "uuid" else String,
                ForeignKey("nested_posts.id"),
                nullable=False,
            )
            text = Column(String, nullable=False)
            is_deleted = Column(Boolean, nullable=False, default=False)
            deleted_at = Column(DateTime(timezone=True), nullable=True)

        base.metadata.create_all(adapter.engine)
        session = adapter.get_async_session if name.endswith("async") else adapter.get_session
        viewset = AsyncBaseViewset if name.endswith("async") else BaseViewset
    elif name == "peewee":
        pw = pytest.importorskip("peewee")
        from fastapi_viewsets.orm.peewee_adapter import PeeweeAdapter

        database = pw.SqliteDatabase(
            str(path), check_same_thread=False, pragmas={"foreign_keys": 1}
        )
        item_database = database

        class Post(pw.Model):
            id = (
                pw.AutoField()
                if id_kind == "int"
                else pw.UUIDField(primary_key=True, default=uuid4)
                if id_kind == "uuid"
                else pw.CharField(primary_key=True, default=lambda: uuid4().hex)
            )
            title = pw.CharField()
            is_deleted = pw.BooleanField(default=False)

            class Meta:
                database = item_database
                table_name = "nested_posts"

        class Comment(pw.Model):
            post = pw.ForeignKeyField(Post, column_name="post_ref", object_id_name="post_id")
            text = pw.CharField()
            is_deleted = pw.BooleanField(default=False)
            deleted_at = pw.DateTimeField(null=True)

            class Meta:
                database = item_database
                table_name = "nested_comments"

        database.create_tables([Post, Comment])
        adapter = PeeweeAdapter(database_url=f"sqlite:///{path}", database=database)
        session, viewset = adapter.get_session, BaseViewset
    else:
        pytest.importorskip("tortoise")
        from fastapi_viewsets.orm.tortoise_adapter import TortoiseAdapter
        from tests.nested_models import NestedComment as Comment
        from tests.nested_models import NestedPost as Post

        if id_kind == "string":
            from tests.nested_models import StringNestedComment as Comment
            from tests.nested_models import StringNestedPost as Post
        elif id_kind == "uuid":
            from tests.nested_models import UUIDNestedComment as Comment
            from tests.nested_models import UUIDNestedPost as Post

        adapter = TortoiseAdapter(database_url=f"sqlite://{path}", models=["tests.nested_models"])
        session, viewset = adapter.get_async_session, AsyncBaseViewset

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

    yield adapter, Post, Comment, session, viewset, lifespan
    if name.startswith("sqlalchemy"):
        adapter.engine.dispose()
    elif name == "peewee":
        database.close()


@pytest.fixture(params=["hard", "boolean", "timestamp"])
def policy(request):
    if request.param == "hard":
        return None
    return SoftDeleteConfig(
        field="is_deleted" if request.param == "boolean" else "deleted_at", mode=request.param
    )


@pytest.fixture
def stack(backend, policy):
    adapter, Post, Comment, session, viewset_class, lifespan = backend
    parent_policy = SoftDeleteConfig()
    posts = viewset_class(
        endpoint="/posts",
        model=Post,
        db_session=session,
        orm_adapter=adapter,
        response_model=PostSchema,
        soft_delete=parent_policy,
    )
    posts.register()

    if viewset_class is AsyncBaseViewset:

        class Comments(AsyncBaseViewset):
            async def resolve_parent(self, request: Request):
                parent = await super().resolve_parent(request)
                if parent is not None and parent.title == "forbidden":
                    raise HTTPException(status_code=403, detail="Forbidden parent")
                return parent

            async def get_element(self, id: int, token=None):
                row = await super().get_element(id, token)
                assert row.post_id == self.get_parent().id
                return row
    else:

        class Comments(BaseViewset):
            def resolve_parent(self, request: Request):
                parent = super().resolve_parent(request)
                if parent is not None and parent.title == "forbidden":
                    raise HTTPException(status_code=403, detail="Forbidden parent")
                return parent

            def get_element(self, id: int, token=None):
                row = super().get_element(id, token)
                assert row.post_id == self.get_parent().id
                return row

    comments = Comments(
        endpoint="/posts/{post_id}/comments",
        model=Comment,
        db_session=session,
        response_model=CommentSchema,
        orm_adapter=adapter,
        soft_delete=policy,
        nested=NestedConfig(
            parent_model=Post, foreign_key="post_id", parent_soft_delete=parent_policy
        ),
    )
    comments.register(
        oauth_protect=OAuth2PasswordBearer(tokenUrl="/token"), protected_methods=["DELETE"]
    )
    app = FastAPI(lifespan=lifespan)
    app.include_router(comments)
    app.include_router(posts)
    with TestClient(app) as client:
        first_response = client.post("/posts", json={"title": "first"})
        assert first_response.status_code == 200, first_response.text
        first = first_response.json()["id"]
        second_response = client.post("/posts", json={"title": "second"})
        assert second_response.status_code == 200, second_response.text
        second = second_response.json()["id"]
        yield client, first, second, comments, policy, app


AUTH = {"Authorization": "Bearer example"}


def create(client, parent, text="comment", **data):
    response = client.post(f"/posts/{parent}/comments", json={"text": text, **data})
    assert response.status_code == 200, response.text
    assert response.json()["postId"] == parent
    return response.json()["id"]


def test_nested_crud_and_foreign_key_binding(stack):
    client, first, second, router, policy, app = stack
    id = create(client, first, postId=second)
    create(client, second, "other")
    url = f"/posts/{first}/comments/{id}"
    assert client.get(url).json()["postId"] == first
    assert len(client.get(f"/posts/{first}/comments").json()) == 1
    for method in ("put", "patch"):
        response = client.request(
            method, url, json={"text": "changed", "postId": second, "post_id": None}
        )
        assert response.status_code == 200, response.text
        assert response.json()["postId"] == first
    assert client.patch(url, json={"postId": second}).status_code == 200
    assert client.get(url).json()["postId"] == first
    assert client.delete(url, headers=AUTH).status_code == 200
    assert client.get(url).status_code == 404
    assert client.get(f"/posts/{first}/comments").json() == []
    if policy is not None:
        assert client.post(url + "/restore", headers=AUTH).status_code == 200
        assert client.get(url).status_code == 200
    else:
        assert client.post(url + "/restore", headers=AUTH).status_code == 404


def test_other_parents_records_cannot_be_accessed_or_mutated(stack):
    client, first, second, router, policy, app = stack
    id = create(client, first)
    wrong = f"/posts/{second}/comments/{id}"
    for method in ("get", "put", "patch", "delete"):
        options = (
            {"json": {"text": "wrong", "postId": second}} if method in ("put", "patch") else {}
        )
        response = client.request(method, wrong, headers=AUTH, **options)
        assert response.status_code == 404, response.text
    assert client.get(f"/posts/{first}/comments/{id}").json()["text"] == "comment"
    assert client.get(f"/posts/{second}/comments").json() == []
    if policy is not None:
        assert client.delete(f"/posts/{first}/comments/{id}", headers=AUTH).status_code == 200
        assert client.post(wrong + "/restore", headers=AUTH).status_code == 404
        assert client.post(f"/posts/{first}/comments/{id}/restore", headers=AUTH).status_code == 200


def test_query_filters_cannot_replace_parent_scope_and_pagination_is_scoped(stack):
    client, first, second, router, policy, app = stack
    create(client, second, "other")
    ids = [create(client, first, text) for text in ("alpha", "bravo", "charlie")]
    base = f"/posts/{first}/comments"
    assert [row["id"] for row in client.get(base + "?limit=1&offset=1").json()] == [ids[1]]
    assert [row["text"] for row in client.get(base + "?search=alpha").json()] == ["alpha"]
    assert [row["id"] for row in client.get(base + "?ordering=-id").json()] == ids[::-1]
    for query in (f"post_id={second}", f"post_id__in={first},{second}", "include_deleted=true"):
        response = client.get(base + "?" + query)
        assert response.status_code == 200, response.text
        assert all(row["postId"] == first for row in response.json())


def test_missing_or_soft_deleted_parent_blocks_all_actions(stack):
    client, first, second, router, policy, app = stack
    id = create(client, first)
    assert client.delete(f"/posts/{first}").status_code == 200
    for parent in (first, 99999):
        base = f"/posts/{parent}/comments"
        for method, suffix in [
            ("get", ""),
            ("post", ""),
            ("get", f"/{id}"),
            ("put", f"/{id}"),
            ("patch", f"/{id}"),
            ("delete", f"/{id}"),
        ]:
            options = {"json": {"text": "changed"}} if method in ("post", "put", "patch") else {}
            assert client.request(method, base + suffix, headers=AUTH, **options).status_code == 404
        if policy is not None:
            assert client.post(base + f"/{id}/restore", headers=AUTH).status_code == 404
    assert client.post(f"/posts/{first}/restore").status_code == 200
    assert client.get(f"/posts/{first}/comments/{id}").status_code == 200


def test_parent_permissions_and_auth_before_lookup(stack):
    client, first, second, router, policy, app = stack
    forbidden = client.post("/posts", json={"title": "forbidden"}).json()["id"]
    assert client.get(f"/posts/{forbidden}/comments").status_code == 403
    assert client.post(f"/posts/{forbidden}/comments", json={"text": "comment"}).status_code == 403
    assert client.delete("/posts/99999/comments/1").status_code == 401
    if policy is not None:
        assert client.post("/posts/99999/comments/1/restore").status_code == 401


def test_model_validation_and_openapi_remain_consistent(stack):
    client, first, second, router, policy, app = stack
    base = f"/posts/{first}/comments"
    assert client.post(base, json={}).status_code == 422
    assert client.post(base, json={"text": "x"}).status_code == 422
    assert client.get("/posts/not-an-integer/comments").status_code == 422
    assert client.get(base).json() == []
    assert CommentSchema.model_fields["post_id"].is_required()
    spec = client.get("/openapi.json")
    assert spec.status_code == 200, spec.text
    spec = spec.json()
    operation = spec["paths"]["/posts/{post_id}/comments"]["post"]
    parent = next(param for param in operation["parameters"] if param["name"] == "post_id")
    assert parent["in"] == "path" and parent["required"]
    assert parent["schema"]["type"] == "integer"
    ref = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    assert "postId" not in spec["components"]["schemas"][ref].get("required", [])
    with pytest.raises(RuntimeError, match="parent_context"):
        router.get_parent()


def test_parallel_requests_do_not_share_parent_context(stack):
    client, first, second, router, policy, app = stack

    def run(number):
        parent = first if number % 2 else second
        id = create(client, parent, f"comment-{number}")
        response = client.get(f"/posts/{parent}/comments/{id}")
        assert response.status_code == 200, response.text
        assert response.json()["postId"] == parent

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(run, range(8)))


def test_external_router_prefix_and_custom_parent_parameter(backend):
    adapter, Post, Comment, session, viewset_class, lifespan = backend
    posts = viewset_class(
        endpoint="/posts",
        model=Post,
        db_session=session,
        orm_adapter=adapter,
        response_model=PostSchema,
    )
    posts.register(methods=["POST"])
    comments = viewset_class(
        endpoint="/comments",
        model=Comment,
        db_session=session,
        orm_adapter=adapter,
        response_model=CommentSchema,
        nested=NestedConfig(
            parent_model=Post,
            foreign_key="post" if not hasattr(Comment, "__table__") else "post_id",
            path_param="post_pk",
        ),
    )
    comments.register(methods=["POST", "LIST"])
    parent_router = APIRouter(prefix="/posts/{post_pk}")
    parent_router.include_router(comments)
    app = FastAPI(lifespan=lifespan)
    app.include_router(posts)
    app.include_router(parent_router)
    with TestClient(app) as client:
        parent = client.post("/posts", json={"title": "parent"}).json()["id"]
        create(client, parent)
        assert len(client.get(f"/posts/{parent}/comments").json()) == 1


def test_invalid_foreign_key_configuration_is_rejected(backend):
    adapter, Post, Comment, session, viewset, lifespan = backend
    for field in ("missing", "id"):
        with pytest.raises(ValueError):
            viewset(
                model=Comment,
                orm_adapter=adapter,
                nested=NestedConfig(parent_model=Post, foreign_key=field, path_param="post_id"),
            )
    with pytest.raises(ValueError, match="different parent"):
        viewset(
            model=Comment,
            orm_adapter=adapter,
            nested=NestedConfig(parent_model=Comment, foreign_key="post_id"),
        )


@pytest.mark.parametrize(
    "backend",
    [
        (name, kind)
        for name in ("sqlalchemy", "sqlalchemy-async", "peewee", "tortoise")
        for kind in ("string", "uuid")
    ],
    indirect=True,
)
def test_string_and_uuid_parent_ids(backend):
    adapter, Post, Comment, session, viewset, lifespan = backend
    id_type = adapter.get_nested_parent_type(Post)
    assert id_type in (str, UUID)
    parent_schema = create_model(
        "TypedParent",
        __config__=ConfigDict(from_attributes=True),
        id=(Optional[id_type], None),
        title=(str, ...),
    )
    child_schema = create_model(
        "TypedChild",
        __config__=ConfigDict(from_attributes=True),
        id=(Optional[int], None),
        post_id=(id_type, ...),
        text=(str, ...),
    )
    posts = viewset(
        endpoint="/posts",
        model=Post,
        db_session=session,
        orm_adapter=adapter,
        response_model=parent_schema,
    )
    posts.register(methods=["POST"])
    comments = viewset(
        endpoint="/posts/{post_id}/comments",
        model=Comment,
        db_session=session,
        orm_adapter=adapter,
        response_model=child_schema,
        nested=NestedConfig(parent_model=Post, foreign_key="post_id"),
    )
    comments.register()
    app = FastAPI(lifespan=lifespan)
    app.include_router(posts)
    app.include_router(comments)
    with TestClient(app) as client:
        response = client.post("/posts", json={"title": "parent"})
        assert response.status_code == 200, response.text
        parent = response.json()["id"]
        response = client.post(f"/posts/{parent}/comments", json={"text": "child"})
        assert response.status_code == 200, response.text
        assert response.json()["post_id"] == parent
        id = response.json()["id"]
        assert client.get(f"/posts/{parent}/comments/{id}").status_code == 200
        other = str(uuid4()) if id_type is UUID else "another-parent"
        assert client.get(f"/posts/{other}/comments/{id}").status_code == 404
        if id_type is UUID:
            assert client.get("/posts/invalid-uuid/comments").status_code == 422


def test_schema_without_foreign_key_and_alias_choices(backend):
    adapter, Post, Comment, session, viewset, lifespan = backend

    class MinimalSchema(BaseModel):
        model_config = ConfigDict(from_attributes=True, extra="forbid")
        id: Optional[int] = None
        text: str

    class AliasedSchema(MinimalSchema):
        post_id: int = Field(validation_alias=AliasChoices("parentId", "post_id"))

    posts = viewset(
        endpoint="/posts",
        model=Post,
        db_session=session,
        orm_adapter=adapter,
        response_model=PostSchema,
    )
    posts.register(methods=["POST"])
    app = FastAPI(lifespan=lifespan)
    app.include_router(posts)
    for endpoint, schema in (("minimal", MinimalSchema), ("aliased", AliasedSchema)):
        router = viewset(
            endpoint=f"/posts/{{post_id}}/{endpoint}",
            model=Comment,
            db_session=session,
            orm_adapter=adapter,
            response_model=schema,
            nested=NestedConfig(parent_model=Post, foreign_key="post_id"),
        )
        router.register()
        app.include_router(router)
    with TestClient(app) as client:
        parent = client.post("/posts", json={"title": "parent"}).json()["id"]
        for endpoint in ("minimal", "aliased"):
            data = {"text": "child", "post_id": 999}
            if endpoint == "aliased":
                data["parentId"] = 999
            response = client.post(f"/posts/{parent}/{endpoint}", json=data)
            assert response.status_code == 200, response.text
        assert client.get("/openapi.json").status_code == 200


@pytest.mark.parametrize(
    "data",
    [
        {"foreign_key": "_private"},
        {"path_param": "id"},
        {"path_param": "token"},
        {"parent_model": None},
    ],
)
def test_invalid_nested_config(data):
    with pytest.raises((ValueError, TypeError)):
        NestedConfig(**{"parent_model": object, "foreign_key": "post_id", **data})


@pytest.mark.parametrize("backend", ["sqlalchemy", "sqlalchemy-async"], indirect=True)
def test_scoped_physical_delete_preserves_orm_cascades(backend):
    from sqlalchemy import Column, ForeignKey, Integer
    from sqlalchemy.orm import relationship

    adapter, Post, Comment, session, viewset, lifespan = backend
    base = adapter.get_base()

    class Attachment(base):
        __tablename__ = "nested_attachments"
        id = Column(Integer, primary_key=True)
        comment_id = Column(Integer, ForeignKey("nested_comments.id"), nullable=False)

    Comment.attachments = relationship(Attachment, cascade="all, delete-orphan", lazy="joined")
    base.metadata.create_all(adapter.engine)
    posts = viewset(
        endpoint="/posts",
        model=Post,
        db_session=session,
        orm_adapter=adapter,
        response_model=PostSchema,
    )
    posts.register(methods=["POST"])
    comments = viewset(
        endpoint="/posts/{post_id}/comments",
        model=Comment,
        db_session=session,
        orm_adapter=adapter,
        response_model=CommentSchema,
        nested=NestedConfig(parent_model=Post, foreign_key="post_id"),
    )
    comments.register()
    app = FastAPI(lifespan=lifespan)
    app.include_router(posts)
    app.include_router(comments)
    with TestClient(app) as client:
        parent = client.post("/posts", json={"title": "parent"}).json()["id"]
        other = client.post("/posts", json={"title": "other"}).json()["id"]
        id = create(client, parent)
        with adapter.get_session() as db:
            db.add(Attachment(comment_id=id))
            db.commit()
        assert client.delete(f"/posts/{other}/comments/{id}").status_code == 404
        with adapter.get_session() as db:
            assert db.query(Attachment).count() == 1
        response = client.patch(f"/posts/{parent}/comments/{id}", json={"text": "updated"})
        assert response.status_code == 200, response.text
        assert client.delete(f"/posts/{parent}/comments/{id}").status_code == 200
        with adapter.get_session() as db:
            assert db.query(Attachment).count() == 0


def test_documented_nested_quickstart_from_installed_wheel(tmp_path):
    import os
    import re
    import subprocess
    import sys
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "docs/nested-resources.md").read_text()
    section = text.split("## Full example\n", 1)[1].split("\n## ", 1)[0]
    snippet = re.search(r"^```python\n(.*?)^```", section, flags=re.M | re.S)
    assert snippet is not None
    checks = """
from fastapi import Depends, Request
from fastapi.testclient import TestClient

@app.get("/posts/{post_id}/summary", response_model=PostSchema,
         dependencies=[Depends(comments.parent_context)])
def summary(post_id: int, request: Request):
    assert comments.get_parent() is request.state.viewset_parent
    return request.state.viewset_parent

with TestClient(app) as client:
    first = client.post("/posts", json={"title": "first"}).json()["id"]
    second = client.post("/posts", json={"title": "second"}).json()["id"]
    response = client.post(f"/posts/{first}/comments", json={"text": "hello", "post_id": second})
    assert response.status_code == 200, response.text
    child = response.json()
    assert child["post_id"] == first
    assert client.get(f"/posts/{second}/comments/{child['id']}").status_code == 404
    assert client.get(f"/posts/{first}/comments/{child['id']}").status_code == 200
    assert client.get(f"/posts/{first}/summary").json()["title"] == "first"
    assert client.get("/posts/99999/summary").status_code == 404
    assert client.delete(f"/posts/{first}/comments/{child['id']}").status_code == 200
    assert client.get(f"/posts/{first}/comments").json() == []
    assert client.get("/openapi.json").status_code == 200
"""
    program = (
        "namespace = {'__name__': 'quickstart'}\n"
        f"exec(compile({snippet.group(1)!r}, 'nested_quickstart', 'exec'), namespace)\n"
        f"exec({checks!r}, namespace)\n"
    )
    env = os.environ.copy()
    for key in (
        "ORM_TYPE",
        "DATABASE_URL",
        "SQLALCHEMY_DATABASE_URL",
        "SQLALCHEMY_ASYNC_DATABASE_URL",
    ):
        env.pop(key, None)
    result = subprocess.run(
        [sys.executable, "-I", "-c", program],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
