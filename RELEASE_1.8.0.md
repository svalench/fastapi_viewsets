# Release 1.8.0

## Permissions

- Optional `permission_classes` on `BaseViewset` / `AsyncBaseViewset`: `BasePermission`, `IsAuthenticated`, `IsOwner`, `IsAdminUser`.
- `has_permission` / `has_object_permission` / `get_scope` hooks; scope is merged into existing ORM filters (nested resources, soft-delete).
- `init_permissions(user_model=User)` plus optional `owner_field` or single-FK auto-detect.
- `register(..., auth_dependency=...)` wires authentication that sets `request.state.user`.
- Foreign row ids return **404**; missing login or explicit object denial returns **403**.
- POST/PUT/PATCH bind the owner column server-side; client owner ids are ignored.

## Compatibility

- Viewsets without `permission_classes` are unchanged.
