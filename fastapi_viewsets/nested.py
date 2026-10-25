"""Request-local parent lookup and binding for opt-in nested resources."""

from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass
from inspect import isawaitable, iscoroutinefunction
from typing import Any, Optional

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from pydantic import (
    AliasChoices,
    BaseModel,
    TypeAdapter,
    ValidationError,
    create_model,
    model_validator,
)
from starlette.concurrency import run_in_threadpool

from fastapi_viewsets.soft_delete import SoftDeleteConfig


@dataclass(frozen=True)
class NestedConfig:
    """Bind a child model's foreign key to a parent ID from the URL.

    Parent and child use the viewset's ORM adapter and session factory. Parent
    models must expose their primary key as ``id``. ``path_param`` defaults to
    ``foreign_key``; configure parent soft deletion explicitly when applicable.
    """

    parent_model: type
    foreign_key: str
    path_param: Optional[str] = None
    parent_soft_delete: Optional[SoftDeleteConfig] = None

    def __post_init__(self) -> None:
        if not isinstance(self.parent_model, type):
            raise TypeError("parent_model must be an ORM model class")
        if self.path_param is None:
            object.__setattr__(self, "path_param", self.foreign_key)
        for name in (self.foreign_key, self.path_param):
            if not isinstance(name, str) or not name.isidentifier() or name.startswith("_"):
                raise ValueError("nested fields and path parameters must be public identifiers")
        if self.path_param in {
            "id",
            "item",
            "token",
            "request",
            "limit",
            "offset",
            "search",
            "ordering",
            "partial",
        }:
            raise ValueError("parent path parameter conflicts with a CRUD parameter")
        if self.parent_soft_delete is not None and not isinstance(
            self.parent_soft_delete, SoftDeleteConfig
        ):
            raise TypeError("parent_soft_delete must be a SoftDeleteConfig or None")


@dataclass(frozen=True)
class _ParentContext:
    viewset: Any
    parent: Any
    parent_id: Any


_CURRENT_PARENT: ContextVar[Optional[_ParentContext]] = ContextVar("viewset_parent", default=None)


class _NestedMixin:
    """Shared integration for synchronous and asynchronous viewsets."""

    def _configure_nested(self, nested: Optional[NestedConfig]) -> None:
        self.nested = nested
        self._nested_models = {}
        if nested is None:
            return
        if not isinstance(nested, NestedConfig):
            raise TypeError("nested must be a NestedConfig or None")
        if self.model is None:
            raise ValueError("nested resources require a child model")
        if not getattr(self.orm_adapter, "supports_nested", False):
            raise ValueError("This ORM adapter does not support nested resources")
        self._nested_field, self._nested_aliases = self.orm_adapter.get_nested_field(
            self.model, nested.foreign_key
        )
        if self.soft_delete is not None and self.soft_delete.field in self._nested_aliases:
            raise ValueError("the parent foreign key cannot be the soft-delete marker")
        if nested.parent_soft_delete is not None:
            self.orm_adapter.validate_soft_delete(nested.parent_model, nested.parent_soft_delete)
        self._parent_id_adapter = TypeAdapter(
            self.orm_adapter.get_nested_parent_type(nested.parent_model)
        )
        self.orm_adapter.validate_nested_parent(self.model, self._nested_field, nested.parent_model)

    def _parent_lookup_args(self, request: Request):
        raw = request.path_params.get(self.nested.path_param)
        try:
            parent_id = self._parent_id_adapter.validate_python(raw)
        except ValidationError as exc:
            errors = [
                dict(error, loc=("path", self.nested.path_param, *error["loc"]))
                for error in exc.errors()
            ]
            raise RequestValidationError(errors) from exc
        options = {}
        if self.nested.parent_soft_delete is not None:
            options["soft_delete"] = self.nested.parent_soft_delete
        return self.nested.parent_model, self.db_session, parent_id, options

    def resolve_parent(self, request: Request) -> Any:
        """Look up the parent; override to add application-specific permissions."""
        model, session, parent_id, options = self._parent_lookup_args(request)
        parent = self.orm_adapter.get_element_by_id(model, session, parent_id, **options)
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent not found")
        return parent

    async def parent_context(self, request: Request):
        """Dependency used automatically by registered nested CRUD routes."""
        if self.nested is None:
            raise HTTPException(status_code=404, detail="Nested resources are not enabled")
        if iscoroutinefunction(self.resolve_parent):
            parent = await self.resolve_parent(request)
        else:
            parent = await run_in_threadpool(self.resolve_parent, request)
            if isawaitable(parent):
                parent = await parent
        if parent is None:
            raise HTTPException(status_code=404, detail="Parent not found")
        context = _ParentContext(self, parent, parent.id)
        token = _CURRENT_PARENT.set(context)
        request.state.viewset_parent = parent
        try:
            yield parent
        finally:
            _CURRENT_PARENT.reset(token)

    def get_parent(self) -> Any:
        """Return the resolved parent in the current handler or dependency."""
        return self._parent_context().parent

    def _parent_context(self) -> _ParentContext:
        context = _CURRENT_PARENT.get()
        if context is None or context.viewset is not self:
            raise RuntimeError("nested operations require this viewset's parent_context dependency")
        return context

    def _orm_options(self) -> dict[str, Any]:
        options = {}
        if self.soft_delete is not None:
            options["soft_delete"] = self.soft_delete
        if self.nested is not None:
            options["scope"] = {self._nested_field: self._parent_context().parent_id}
        return options

    def _nested_body_model(self, model: type[BaseModel]) -> type[BaseModel]:
        cached = self._nested_models.get(model)
        if cached is not None:
            return cached
        bindings = []
        fields = {}
        for name, info in model.model_fields.items():
            if name not in self._nested_aliases:
                continue
            alias = info.validation_alias if info.validation_alias is not None else info.alias
            aliases = alias.choices if isinstance(alias, AliasChoices) else [alias]
            # Flat FK fields may use string aliases or AliasChoices. Deep
            # AliasPath fields would ambiguously edit other request objects.
            if any(value is not None and not isinstance(value, str) for value in aliases):
                raise ValueError("nested foreign-key fields require flat string validation aliases")
            keys = {name, *(value for value in aliases if value is not None)}
            key = (
                aliases[0]
                if aliases[0] is not None and model.model_config.get("validate_by_alias", True)
                else name
            )
            bindings.append((keys, key))
            field = deepcopy(info)
            field.default = None
            field.default_factory = None
            field.validate_default = False
            fields[name] = (info.annotation, field)

        def bind_parent(cls, value):
            if not isinstance(value, dict):
                return value
            data = dict(value)
            for name in self._nested_aliases:
                data.pop(name, None)
            parent_id = self._parent_context().parent_id
            for keys, key in bindings:
                for candidate in keys:
                    data.pop(candidate, None)
                data[key] = parent_id
            return data

        nested_model = create_model(
            f"{model.__name__}Nested",
            __base__=model,
            __validators__={
                "_bind_nested_parent": model_validator(mode="before")(classmethod(bind_parent))
            },
            **fields,
        )
        self._nested_models[model] = nested_model
        return nested_model

    def _nested_openapi_extra(self, extra):
        if self.nested is None:
            return extra
        return {
            **(extra or {}),
            "parameters": [
                *(extra or {}).get("parameters", []),
                {
                    "name": self.nested.path_param,
                    "in": "path",
                    "required": True,
                    "schema": self._parent_id_adapter.json_schema(),
                    "description": "Parent resource ID.",
                },
            ],
        }
