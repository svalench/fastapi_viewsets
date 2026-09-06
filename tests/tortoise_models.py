"""Shared Tortoise ORM models for tests.

These models live at module level (as required by Tortoise) and are
referenced by tests via ``models=["tests.tortoise_models"]`` so that
``Tortoise.init()`` can discover and register them properly.

The module is only imported from tests that already know tortoise-orm
is installed; importing it without tortoise-orm raises ``ImportError``,
which those tests translate into a skip.
"""

from tortoise import fields
from tortoise.models import Model


class SimpleTortoiseModel(Model):
    """Model with a required ``name`` and an optional ``value``."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)
    value = fields.IntField(null=True)


class UniqueNameTortoiseModel(Model):
    """Model with a unique constraint on ``name`` (for IntegrityError tests)."""

    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50, unique=True)
