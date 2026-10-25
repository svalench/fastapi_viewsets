"""Opt-in soft deletion shared by all built-in ORM adapters."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal


@dataclass(frozen=True)
class SoftDeleteConfig:
    """Describe a model's deletion marker.

    ``boolean`` uses ``False`` for active rows and ``True`` for deleted rows.
    ``timestamp`` uses ``None`` for active rows and a UTC datetime for deleted
    rows. The application must add/migrate the column before enabling this.
    """

    field: str = "is_deleted"
    mode: Literal["boolean", "timestamp"] = "boolean"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.field, str)
            or not self.field.isidentifier()
            or self.field.startswith("_")
        ):
            raise ValueError("soft-delete field must be a public model field name")
        if self.mode not in ("boolean", "timestamp"):
            raise ValueError("soft-delete mode must be 'boolean' or 'timestamp'")

    @property
    def active_value(self) -> Any:
        """Database value identifying an active record."""
        return False if self.mode == "boolean" else None

    def deleted_value(self) -> Any:
        """Database value written by DELETE."""
        return True if self.mode == "boolean" else datetime.now(timezone.utc)

    def create_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """New records always start active, regardless of client input."""
        return {**data, self.field: self.active_value}

    def update_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Only DELETE/RESTORE may change the deletion marker."""
        return {key: value for key, value in data.items() if key != self.field}
