"""PATCH must relax field presence without relaxing validation of supplied values."""
from typing import ClassVar, Optional

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from fastapi_viewsets import BaseViewset
from fastapi_viewsets._register import _build_partial_model


class ValidatedItem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    name: str = Field(min_length=2, max_length=20, alias="displayName")
    price: int = Field(ge=0)
    note: Optional[str] = None

    @field_validator("name")
    @classmethod
    def reject_reserved_name(cls, value):
        if value == "reserved":
            raise ValueError("reserved name")
        return value


@pytest.mark.parametrize("payload", [
    {"displayName": "x"}, {"displayName": "x" * 21},
    {"price": -1}, {"displayName": "reserved"},
    {"name": None}, {"unexpected": "value"},
])
def test_patch_preserves_validation(payload):
    with pytest.raises(ValidationError):
        _build_partial_model(ValidatedItem)(**payload)


def test_patch_preserves_aliases_and_unset_fields():
    partial = _build_partial_model(ValidatedItem)
    assert partial(displayName="valid").model_dump(exclude_unset=True) == {"name": "valid"}
    assert partial(note=None).model_dump(exclude_unset=True) == {"note": None}
    assert partial().model_dump(exclude_unset=True) == {}
    assert ValidatedItem.model_fields["name"].is_required()
    assert partial is _build_partial_model(ValidatedItem)


def test_invalid_patch_never_reaches_database():
    from unittest.mock import Mock
    adapter = Mock()
    viewset = BaseViewset(endpoint="/items", model=Mock(), response_model=ValidatedItem,
                          orm_adapter=adapter, db_session=Mock())
    viewset.register(methods=["PATCH"])
    app = FastAPI()
    app.include_router(viewset)
    with TestClient(app) as client:
        response = client.patch("/items/1", json={"price": -1})
    assert response.status_code == 422
    adapter.update_element.assert_not_called()


def test_cross_field_model_validators_do_not_run_on_incomplete_patch():
    class Interval(BaseModel):
        start: int
        end: int

        @model_validator(mode="after")
        def validate_interval(self):
            if self.start > self.end:
                raise ValueError("start must precede end")
            return self

    partial = _build_partial_model(Interval)
    assert partial(start=1).model_dump(exclude_unset=True) == {"start": 1}
    assert partial().model_dump(exclude_unset=True) == {}
    with pytest.raises(ValidationError):
        Interval(start=2, end=1)


def test_field_validator_keeps_original_class_binding():
    class Parent(BaseModel):
        name: str
        ALLOWED: ClassVar[set] = {"allowed"}

        @classmethod
        def allowed(cls, value):
            return value in cls.ALLOWED

    class Child(Parent):
        @field_validator("name")
        @classmethod
        def check_allowed(cls, value):
            if not super().allowed(value):
                raise ValueError("name is forbidden")
            return value

    partial = _build_partial_model(Child)
    assert partial(name="allowed").name == "allowed"
    with pytest.raises(ValidationError):
        partial(name="forbidden")
