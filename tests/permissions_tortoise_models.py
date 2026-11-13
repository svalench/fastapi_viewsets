"""Tortoise-модели для кросс-ORM тестов permissions."""

from tortoise import fields
from tortoise.models import Model


class PermAccount(Model):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=50)
    is_staff = fields.BooleanField(default=False)

    class Meta:
        table = "perm_t_accounts"


class PermOwnedItem(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=100)
    user = fields.ForeignKeyField("models.PermAccount", related_name="owned_items")
    is_deleted = fields.BooleanField(default=False)

    class Meta:
        table = "perm_t_owned_items"


class PermDualOwnerItem(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=100)
    user = fields.ForeignKeyField("models.PermAccount", related_name="dual_primary")
    editor = fields.ForeignKeyField("models.PermAccount", related_name="dual_edited")

    class Meta:
        table = "perm_t_dual_owner"


class PermFolder(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=50)

    class Meta:
        table = "perm_t_folders"


class PermDocument(Model):
    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=100)
    folder = fields.ForeignKeyField("models.PermFolder", related_name="documents")
    user = fields.ForeignKeyField("models.PermAccount", related_name="documents")

    class Meta:
        table = "perm_t_documents"
