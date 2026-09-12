"""Shared route registration logic for sync and async viewsets.

Both ``BaseViewset`` and ``AsyncBaseViewset`` need to wire CRUD methods
into FastAPI ``APIRouter`` routes in exactly the same way. The logic is
collected here as a mixin to avoid two divergent copies.
"""

from __future__ import annotations

import functools
import types
from collections.abc import Iterable
from typing import Any, Dict, List, Optional, Type

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, create_model

from fastapi_viewsets.constants import MAP_METHODS

# Routing order matters: routes without path parameters must be added
# before routes that use them, otherwise FastAPI may match LIST against
# the ``/{id}`` route.
_METHOD_ORDER = ("LIST", "POST", "GET", "PUT", "PATCH", "DELETE")

# Cache of generated partial (all-optional) PATCH body models, keyed by
# the source schema, so repeated ``register()`` calls reuse one model.
_PARTIAL_MODEL_CACHE: Dict[type, type] = {}


def _build_partial_model(model: Type[BaseModel]) -> Type[BaseModel]:
    """Build an all-optional variant of a Pydantic schema for PATCH bodies.

    PATCH semantics require that clients may send any subset of fields,
    so required fields in the response schema must become optional in
    the request body. Unset fields are excluded later via
    ``model_dump(exclude_unset=True)``; explicitly sent ``null`` values
    are preserved so nullable columns can be cleared.
    """
    cached = _PARTIAL_MODEL_CACHE.get(model)
    if cached is not None:
        return cached

    if not hasattr(model, "model_fields"):  # pragma: no cover - pydantic v1 fallback
        return model

    fields: Dict[str, Any] = {}
    for name, field_info in model.model_fields.items():
        fields[name] = (Optional[field_info.annotation], None)

    partial = create_model(f"{model.__name__}Patch", **fields)
    _PARTIAL_MODEL_CACHE[model] = partial
    return partial


def _clone_bound_method(bound: Any, annotation_overrides: Dict[str, Any]) -> Any:
    """Return a per-instance copy of a bound method with patched annotations.

    ``register()`` is called once per viewset instance, but CRUD handlers
    are functions defined once on the class. Mutating
    ``handler.__annotations__`` directly would leak one viewset's body
    schema into every other viewset in the process, so the function is
    cloned first and the clone's annotations are patched instead.
    """
    func = getattr(bound, "__func__", None)
    if func is None:
        # Not a plain bound method (already a partial/closure): patch a
        # fresh annotation dict on the object itself, best-effort.
        try:
            merged = {**getattr(bound, "__annotations__", {}), **annotation_overrides}
            bound.__annotations__ = merged
        except (AttributeError, TypeError):
            pass
        return bound

    new_func = types.FunctionType(
        func.__code__,
        func.__globals__,
        func.__name__,
        func.__defaults__,
        func.__closure__,
    )
    new_func.__dict__.update(func.__dict__)
    new_func.__kwdefaults__ = func.__kwdefaults__
    new_func.__annotations__ = {**func.__annotations__, **annotation_overrides}
    new_func.__doc__ = func.__doc__
    new_func.__module__ = func.__module__
    new_func.__qualname__ = func.__qualname__
    return types.MethodType(new_func, bound.__self__)


class _RegisterMixin:
    """Mixin providing :meth:`register` for CRUD endpoint wiring.

    Subclasses are expected to expose ``self.endpoint``, ``self.tags``,
    ``self.response_model`` and the CRUD handlers
    (``list``, ``get_element``, ``create_element``, ``update_element``,
    ``delete_element``) used by :data:`MAP_METHODS`.
    """

    ALLOWED_METHODS: List[str]

    def register(
        self,
        methods: Optional[List[str]] = None,
        oauth_protect: Optional[OAuth2PasswordBearer] = None,
        protected_methods: Optional[List[str]] = None,
    ) -> None:
        """Register CRUD endpoints on this router.

        Args:
            methods: Logical methods to register. Defaults to all
                allowed methods. Allowed values:
                ``LIST``, ``GET``, ``POST``, ``PUT``, ``PATCH``,
                ``DELETE``.
            oauth_protect: ``OAuth2PasswordBearer`` instance used as a
                FastAPI dependency on protected operations.
            protected_methods: Subset of ``methods`` that should require
                the bearer token. Ignored if ``oauth_protect`` is None.
        """
        protected_methods = list(protected_methods or [])

        if methods is None:
            methods = list(self.ALLOWED_METHODS)
        if not isinstance(methods, Iterable):
            raise ValueError(
                'methods must be List of methods (e.g. ["GET"])'
            )

        # Sort so LIST is registered before GET/{id}.
        sorted_methods = sorted(
            methods,
            key=lambda m: _METHOD_ORDER.index(m) if m in _METHOD_ORDER else len(_METHOD_ORDER),
        )

        for method in sorted_methods:
            spec = MAP_METHODS.get(method)
            if not spec:
                raise ValueError(
                    f"Unknown method: {method}. "
                    f"Allowed methods: {list(MAP_METHODS.keys())}"
                )

            handler = getattr(self, spec["method"])

            # Hint FastAPI/Pydantic about the body schema if the handler
            # carries an ``item`` parameter. The handler is cloned first
            # so patching never mutates the shared class-level function
            # (which would leak this viewset's schema into other
            # viewsets). PATCH gets an all-optional partial model so
            # clients may send any subset of fields.
            if self.response_model is not None and "item" in getattr(
                handler, "__annotations__", {}
            ):
                body_model = self.response_model
                if spec["http_method"] == "PATCH":
                    body_model = _build_partial_model(self.response_model)
                handler = _clone_bound_method(handler, {"item": body_model})

            original_doc = handler.__doc__

            # PUT vs PATCH share an underlying handler but differ in the
            # ``partial`` flag.
            if spec["method"] == "update_element":
                handler = functools.partial(
                    handler, partial=method == "PATCH"
                )
                handler.__doc__ = original_doc

            if method in protected_methods and oauth_protect is not None:
                handler = functools.partial(handler, token=Depends(oauth_protect))
                handler.__doc__ = original_doc

            endpoint = (self.endpoint or "") + spec.get("path", "")
            response_model = self._build_response_model(spec)
            route_name = self._build_route_name(method)
            openapi_extra = self._build_openapi_extra(spec)

            self.add_api_route(
                endpoint,
                handler,
                response_model=response_model,
                tags=self.tags,
                methods=[spec["http_method"]],
                name=route_name,
                openapi_extra=openapi_extra,
            )

    # --- helpers ---------------------------------------------------

    def _build_openapi_extra(self, spec) -> Optional[Dict[str, Any]]:
        """Document dynamic LIST filter parameters in OpenAPI.

        Filters are parsed from ``request.query_params`` at runtime, so
        FastAPI cannot see them in the handler signature. Advertise the
        whitelisted ``ListConfig.filters`` fields (and their ``__op``
        variants) explicitly via ``openapi_extra``.
        """
        if not spec.get("is_list") or self.response_model is None:
            return None

        from fastapi_viewsets.filtering import FILTER_OPS, get_list_config

        config = get_list_config(self.response_model)
        if not config.filters:
            return None

        parameters: List[Dict[str, Any]] = []
        for field_name in config.filters:
            parameters.append(
                {
                    "name": field_name,
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": f"Exact-match filter on `{field_name}`.",
                }
            )
            for op in FILTER_OPS:
                parameters.append(
                    {
                        "name": f"{field_name}__{op}",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "string"},
                        "description": f"Comparison filter `{op}` on `{field_name}`.",
                    }
                )
        return {"parameters": parameters}

    def _build_response_model(self, spec):
        """Compute the FastAPI ``response_model`` for a given method spec."""
        if spec.get("http_method") == "DELETE":
            return None
        if self.response_model is None:
            return None
        if spec.get("is_list"):
            return List[self.response_model]
        return self.response_model

    def _build_route_name(self, method: str) -> str:
        """Build a stable route name for OpenAPI/url_path_for."""
        endpoint = self.endpoint or ""
        slug = endpoint.replace("/", "_").strip("_") or "root"
        return f"{method.lower()}_{slug}"
