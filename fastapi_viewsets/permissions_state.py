"""Состояние конфигурации permissions (модель пользователя)."""

from __future__ import annotations

from typing import Optional

_USER_MODEL: Optional[type] = None


def set_user_model(user_model: type) -> None:
    global _USER_MODEL
    _USER_MODEL = user_model


def get_user_model() -> Optional[type]:
    return _USER_MODEL
