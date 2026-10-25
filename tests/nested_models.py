"""Models for nested-resource tests, registered only under the models app.

Keep these separate from generic adapter fixtures, which are registered under
multiple app labels and therefore must not contain fixed-label FK references.
"""

from uuid import uuid4

from tortoise import fields
from tortoise.models import Model


class NestedPost(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=50)
    is_deleted = fields.BooleanField(default=False)

    class Meta:
        table = "nested_posts"


class NestedComment(Model):
    id = fields.IntField(pk=True)
    post = fields.ForeignKeyField(
        "models.NestedPost", related_name="comments", source_field="post_ref"
    )
    text = fields.CharField(max_length=100)
    is_deleted = fields.BooleanField(default=False)
    deleted_at = fields.DatetimeField(null=True)

    class Meta:
        table = "nested_comments"


class StringNestedPost(Model):
    id = fields.CharField(max_length=36, pk=True, default=lambda: uuid4().hex)
    title = fields.CharField(max_length=50)


class StringNestedComment(Model):
    id = fields.IntField(pk=True)
    post = fields.ForeignKeyField("models.StringNestedPost", related_name="comments")
    text = fields.CharField(max_length=100)


class UUIDNestedPost(Model):
    id = fields.UUIDField(pk=True, default=uuid4)
    title = fields.CharField(max_length=50)


class UUIDNestedComment(Model):
    id = fields.IntField(pk=True)
    post = fields.ForeignKeyField("models.UUIDNestedPost", related_name="comments")
    text = fields.CharField(max_length=100)
