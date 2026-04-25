"""Shared route registration logic for sync and async viewsets.

Both ``BaseViewset`` and ``AsyncBaseViewset`` need to wire CRUD methods
into FastAPI ``APIRouter`` routes in exactly the same way. The logic is
collected here as a mixin to avoid two divergent copies.
"""

from __future__ import annotations

import functools
from collections.abc import Iterable
from typing import List, Optional

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from fastapi_viewsets.constants import MAP_METHODS

# Routing order matters: routes without path parameters must be added
# before routes that use them, otherwise FastAPI may match LIST against
# the ``/{id}`` route.
_METHOD_ORDER = ("LIST", "POST", "GET", "PUT", "PATCH", "DELETE")


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
            # carries an ``item`` parameter. Annotation patching is
            # best-effort: built-in/bound methods may reject it.
            if self.response_model is not None and "item" in getattr(
                handler, "__annotations__", {}
            ):
                try:
                    handler.__annotations__["item"] = self.response_model
                except (AttributeError, TypeError):
                    pass

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

            self.add_api_route(
                endpoint,
                handler,
                response_model=response_model,
                tags=self.tags,
                methods=[spec["http_method"]],
                name=route_name,
            )

    # --- helpers ---------------------------------------------------

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
