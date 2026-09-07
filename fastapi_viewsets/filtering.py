"""Server-side search, ordering and filtering for LIST endpoints.

Configuration is declarative: a Pydantic response schema may declare an
inner ``ListConfig`` class::

    class UserSchema(BaseModel):
        class RelatedConfig:
            select_related = ["company"]

        class ListConfig:
            search_fields = ["name", "email"]
            ordering_fields = ["name", "created_at"]
            ordering = ["-created_at"]
            filters = ["status", "age", "company_id"]

The viewset ``list`` handler then automatically supports:

* ``?search=term`` — case-insensitive substring match, OR-ed across
  ``search_fields``.
* ``?ordering=-name,created_at`` — ordering validated against
  ``ordering_fields``; a leading ``-`` means descending. When the query
  parameter is omitted (or ordering is not enabled), the declarative
  default ``ordering`` applies.
* ``?<field>=value`` and ``?<field>__<op>=value`` — exact-match and
  comparison filtering, restricted to the fields listed in ``filters``.
  Supported operators: ``ne``, ``gt``, ``gte``, ``lt``, ``lte``,
  ``contains`` (case-insensitive substring) and ``in``
  (comma-separated values).

All configuration is optional; without a ``ListConfig`` the LIST
endpoint behaves exactly as before (backward compatible).
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field as dc_field
from typing import Any, Dict, List, Mapping, Optional, Tuple, Type

from fastapi import HTTPException
from pydantic import BaseModel
from starlette import status

# Operators accepted after a field name in query params: ?age__gte=18
FILTER_OPS = ("ne", "gt", "gte", "lt", "lte", "contains", "in")


@dataclass(frozen=True)
class ListConfig:
    """Declarative LIST configuration read from a schema's ``ListConfig``."""

    search_fields: List[str] = dc_field(default_factory=list)
    ordering_fields: List[str] = dc_field(default_factory=list)
    ordering: List[str] = dc_field(default_factory=list)
    filters: List[str] = dc_field(default_factory=list)


def get_list_config(response_model: Optional[Type[BaseModel]]) -> ListConfig:
    """Read ``ListConfig`` from a Pydantic schema (if present).

    Args:
        response_model: Pydantic BaseModel subclass that may define an
            inner ``ListConfig`` class.

    Returns:
        A :class:`ListConfig` with whatever attributes were declared;
        an all-empty config when the schema declares nothing.
    """
    if response_model is None:
        return ListConfig()
    cfg = getattr(response_model, "ListConfig", None)
    if cfg is None:
        return ListConfig()
    return ListConfig(
        search_fields=list(getattr(cfg, "search_fields", []) or []),
        ordering_fields=list(getattr(cfg, "ordering_fields", []) or []),
        ordering=list(getattr(cfg, "ordering", []) or []),
        filters=list(getattr(cfg, "filters", []) or []),
    )


def coerce_value(raw: str) -> Any:
    """Coerce a raw query-param string to int/float/bool when possible.

    Args:
        raw: Raw string value from a query parameter.

    Returns:
        ``int``, ``float`` or ``bool`` when the string parses as one,
        otherwise the original string.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def parse_ordering_param(
    ordering: Optional[str],
    ordering_fields: Optional[List[str]] = None,
    default: Optional[List[str]] = None,
) -> Optional[List[str]]:
    """Parse the ``ordering`` query parameter into ordering tokens.

    Args:
        ordering: Raw ``?ordering=`` value, e.g. ``"-name,created_at"``.
        ordering_fields: Whitelist of fields that may be used. When
            empty/None the whitelist is not enforced.
        default: Declarative default ordering used when ``ordering`` is
            empty or None.

    Returns:
        List of tokens such as ``["-name", "created_at"]``, or None when
        neither the parameter nor a default is provided.

    Raises:
        HTTPException: 400 when the parameter references a field outside
            ``ordering_fields``.
    """
    if ordering is None or not ordering.strip():
        return list(default) if default else None

    allowed = set(ordering_fields or [])
    if not allowed:
        # Ordering is not enabled for this schema; ignore the parameter
        # so arbitrary field names never reach the ORM.
        return list(default) if default else None

    tokens = [token.strip() for token in ordering.split(",") if token.strip()]
    for token in tokens:
        field_name = token.lstrip("-").strip()
        if allowed and field_name not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Invalid ordering field: '{field_name}'. "
                    f"Allowed fields: {sorted(allowed)}"
                ),
            )
    return tokens or (list(default) if default else None)


def parse_filters(
    query_params: Mapping[str, Any],
    allowed_fields: Optional[List[str]] = None,
) -> Dict[str, Tuple[str, Any]]:
    """Extract filter constraints from request query parameters.

    Only fields listed in ``allowed_fields`` are extracted; everything
    else (including ``limit``, ``offset``, ``search`` and ``ordering``)
    is ignored.

    Args:
        query_params: Query parameters mapping (e.g.
            ``request.query_params``).
        allowed_fields: Whitelist of filterable field names.

    Returns:
        Mapping ``field -> (operator, value)`` where operator is one of
        ``"eq"``, ``"ne"``, ``"gt"``, ``"gte"``, ``"lt"``, ``"lte"``,
        ``"contains"``, ``"in"``. For ``"in"`` the value is a list.
    """
    allowed = set(allowed_fields or [])
    if not allowed:
        return {}

    filters: Dict[str, Tuple[str, Any]] = {}
    for key, raw in query_params.items():
        if key in ("limit", "offset", "search", "ordering", "token"):
            continue
        if key not in allowed:
            # Maybe an operator suffix: field__op
            if "__" in key:
                base, op = key.rsplit("__", 1)
                if base in allowed and op in FILTER_OPS:
                    value: Any = (
                        [coerce_value(part) for part in str(raw).split(",")]
                        if op == "in"
                        else coerce_value(raw)
                    )
                    filters[base] = (op, value)
            continue
        if raw is None or str(raw) == "":
            continue
        filters[key] = ("eq", coerce_value(raw))
    return filters
