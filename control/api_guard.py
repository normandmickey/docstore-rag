from rest_framework.exceptions import PermissionDenied

from .api_auth import get_api_key_from_header
from .models import Tenant, Workspace


def resolve_request_context(request, *, tenant_id=None, workspace_id=None):
    if request.user.is_authenticated:
        if tenant_id is None or workspace_id is None:
            raise PermissionDenied('Signed-in requests must include tenant_id and workspace_id.')
        tenant = Tenant.objects.get(id=tenant_id)
        workspace = Workspace.objects.get(id=workspace_id, tenant=tenant)
        return tenant, workspace, None

    api_key = get_api_key_from_header(request)
    if not api_key:
        raise PermissionDenied('Authentication required. Provide a valid Bearer API key or sign in.')

    tenant = api_key.tenant
    if api_key.workspace_id:
        workspace = api_key.workspace
        if workspace_id is not None and workspace_id != workspace.id:
            raise PermissionDenied('API key is not scoped to this workspace.')
        return tenant, workspace, api_key

    if workspace_id is None:
        raise PermissionDenied('workspace_id is required for tenant-wide API keys.')
    workspace = Workspace.objects.get(id=workspace_id, tenant=tenant)
    return tenant, workspace, api_key
