"""Опциональные DRF-подобные permission-классы для viewset'ов."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Type, Union

from fastapi import HTTPException, Request
from pydantic import AliasChoices, BaseModel, create_model, model_validator
from starlette import status

from fastapi_viewsets.permissions_state import get_user_model


class BasePermission:
    """Базовый permission: проверка действия, объекта и SQL-scope."""

    def has_permission(self, request: Request, view: Any, action: str) -> bool:
        """Можно ли вызвать action без загрузки конкретной строки."""
        return True

    def has_object_permission(self, request: Request, view: Any, action: str, obj: Any) -> bool:
        """Можно ли работать с уже загруженным объектом."""
        return True

    def get_scope(self, request: Request, view: Any) -> Dict[str, Any]:
        """Дополнительные equality-фильтры для LIST и get-by-id."""
        return {}

    def filter_queryset(self, request: Request, view: Any, queryset: Any) -> Any:
        """Точка расширения для OR/joins; по умолчанию queryset не меняется."""
        return queryset


def _current_user(request: Request) -> Any:
    return getattr(request.state, "user", None)


def _user_pk(user: Any) -> Any:
    if user is None:
        return None
    if hasattr(user, "id") and user.id is not None:
        return user.id
    return getattr(user, "pk", None)


def _is_privileged(user: Any) -> bool:
    if user is None:
        return False
    for flag in ("is_staff", "is_admin", "staff"):
        if bool(getattr(user, flag, False)):
            return True
    return False


class IsAuthenticated(BasePermission):
    """Требует аутентифицированного пользователя на ``request.state.user``."""

    def has_permission(self, request: Request, view: Any, action: str) -> bool:
        return _current_user(request) is not None


class IsAdminUser(BasePermission):
    """Только staff/admin пользователи."""

    def has_permission(self, request: Request, view: Any, action: str) -> bool:
        return _is_privileged(_current_user(request))


IsAdmin = IsAdminUser


class IsOwner(BasePermission):
    """Ограничивает queryset владельцем; staff видит все записи."""

    def __init__(self, field: Optional[str] = None) -> None:
        self.field = field

    def _owner_field(self, view: Any) -> str:
        if self.field is not None:
            return self.field
        resolved = getattr(view, "_resolved_owner_field", None)
        if resolved is None:
            raise RuntimeError("IsOwner requires owner_field or a single User foreign key")
        return resolved

    def has_permission(self, request: Request, view: Any, action: str) -> bool:
        return _current_user(request) is not None

    def has_object_permission(self, request: Request, view: Any, action: str, obj: Any) -> bool:
        user = _current_user(request)
        if _is_privileged(user):
            return True
        field = self._owner_field(view)
        return getattr(obj, field, None) == _user_pk(user)

    def get_scope(self, request: Request, view: Any) -> Dict[str, Any]:
        user = _current_user(request)
        if user is None or _is_privileged(user):
            return {}
        field = self._owner_field(view)
        pk = _user_pk(user)
        if pk is None:
            return {}
        return {field: pk}


class _PermissionsMixin:
    """Интеграция permission_classes в CRUD и scope."""

    permission_classes: ClassVar[Sequence[Type[BasePermission]]] = ()
    owner_field: Optional[str] = None

    def _configure_permissions(self) -> None:
        classes = tuple(getattr(type(self), "permission_classes", None) or ())
        field_override = getattr(self, "owner_field", None)
        if field_override is None:
            field_override = getattr(type(self), "owner_field", None)

        self._permissions: List[BasePermission] = [cls() for cls in classes]
        self._resolved_owner_field: Optional[str] = None
        self._owner_aliases: tuple[str, ...] = ()
        self._permission_models: Dict[type[BaseModel], type[BaseModel]] = {}

        if not self._permissions:
            return

        needs_owner = field_override is not None or any(
            isinstance(permission, IsOwner) for permission in self._permissions
        )
        if not needs_owner:
            return
        if self.model is None:
            raise ValueError("owner-scoped permissions require a model")

        explicit_field = field_override
        if explicit_field is None:
            for permission in self._permissions:
                if isinstance(permission, IsOwner) and permission.field is not None:
                    explicit_field = permission.field
                    break

        if explicit_field is not None:
            self._resolved_owner_field = explicit_field
        else:
            user_model = get_user_model()
            if user_model is None:
                raise ValueError(
                    "call init_permissions(user_model=...) before using IsOwner without owner_field"
                )
            matches = self.orm_adapter.discover_user_foreign_keys(self.model, user_model)
            if len(matches) == 0:
                raise ValueError(
                    "cannot auto-detect owner_field: no foreign key to the configured user model; "
                    "set owner_field on the viewset or IsOwner(field=...)"
                )
            if len(matches) > 1:
                raise ValueError(
                    "cannot auto-detect owner_field: multiple user foreign keys found "
                    f"({', '.join(matches)}); set owner_field explicitly"
                )
            self._resolved_owner_field = matches[0]

        canonical, aliases = self.orm_adapter.get_nested_field(self.model, self._resolved_owner_field)
        self._resolved_owner_field = canonical
        self._owner_aliases = aliases

    def _action_from_partial(self, partial: bool) -> str:
        return "PATCH" if partial else "PUT"

    def _deny(self) -> None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    def _check_permissions(self, request: Optional[Request], action: str) -> None:
        if not self._permissions or request is None:
            return
        for permission in self._permissions:
            if not permission.has_permission(request, self, action):
                self._deny()

    def _check_object_permissions(self, request: Optional[Request], action: str, obj: Any) -> None:
        if not self._permissions or request is None or obj is None:
            return
        for permission in self._permissions:
            if not permission.has_object_permission(request, self, action, obj):
                self._deny()

    def _permission_scope(self, request: Optional[Request]) -> Dict[str, Any]:
        if not self._permissions or request is None:
            return {}
        scope: Dict[str, Any] = {}
        for permission in self._permissions:
            scope.update(permission.get_scope(request, self) or {})
        return scope

    def _orm_options(self, request: Optional[Request] = None) -> Dict[str, Any]:
        options = super()._orm_options()  # type: ignore[misc]
        permission_scope = self._permission_scope(request)
        if permission_scope:
            existing = dict(options.get("scope") or {})
            options["scope"] = {**permission_scope, **existing}
        return options

    def _create_options(self, request: Optional[Request]) -> Dict[str, Any]:
        options = self._orm_options(request)
        if self._resolved_owner_field and request is not None:
            user = _current_user(request)
            pk = _user_pk(user)
            if pk is not None:
                scope = dict(options.get("scope") or {})
                scope[self._resolved_owner_field] = pk
                options["scope"] = scope
        return options

    def _permission_body_model(self, model: type[BaseModel]) -> type[BaseModel]:
        if self._resolved_owner_field is None:
            return model
        cached = self._permission_models.get(model)
        if cached is not None:
            return cached

        fields = {}
        bindings: list[tuple[set[str], str]] = []
        for name, info in model.model_fields.items():
            if name not in self._owner_aliases:
                continue
            alias = info.validation_alias if info.validation_alias is not None else info.alias
            aliases = alias.choices if isinstance(alias, AliasChoices) else [alias]
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

        def strip_owner(cls, value):
            if not isinstance(value, dict):
                return value
            data = dict(value)
            for keys, key in bindings:
                for candidate in keys:
                    data.pop(candidate, None)
                data.pop(key, None)
            return data

        patched = create_model(
            f"{model.__name__}Owned",
            __base__=model,
            __validators__={"_strip_owner": model_validator(mode="before")(classmethod(strip_owner))},
            **fields,
        )
        self._permission_models[model] = patched
        return patched

    def uses_permissions(self) -> bool:
        return bool(self._permissions)


def init_permissions(*, user_model: type) -> None:
    """Глобально задаёт модель пользователя для auto-detect owner_field."""
    from fastapi_viewsets.permissions_state import set_user_model

    set_user_model(user_model)


def get_user(request: Request) -> Any:
    """Возвращает текущего пользователя с ``request.state.user``."""
    return _current_user(request)
