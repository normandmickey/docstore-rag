from rest_framework.exceptions import PermissionDenied

from .api_auth import get_api_key_from_header


def resolve_api_context(request, *, tenant, workspace):
    if request.user.is_authenticated:
        return None

    api_key = get_api_key_from_header(request)
    if not api_key:
        raise PermissionDenied('Authentication required. Provide a valid Bearer API key or sign in.')
    if api_key.tenant_id != tenant.id:
        raise PermissionDenied('API key does not belong to this tenant.')
    if api_key.workspace_id and api_key.workspace_id != workspace.id:
        raise PermissionDenied('API key is not scoped to this workspace.')
    return api_key
