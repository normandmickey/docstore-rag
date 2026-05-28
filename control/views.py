import logging

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.text import slugify

from documents.models import Document
from ingestion.models import IngestionJob
from ingestion.tasks import ingest_document_task

from .forms import SignUpForm
from .models import Tenant, TenantMembership, Workspace

logger = logging.getLogger(__name__)


class AppLoginView(LoginView):
    template_name = 'auth/login.html'
    redirect_authenticated_user = True


def logout_view(request):
    logout(request)
    return redirect('login')


def _bootstrap_user_workspace(user, session):
    memberships = TenantMembership.objects.select_related('tenant').filter(user=user).order_by('created_at')
    if not memberships.exists():
        base = slugify(user.username) or f'user-{user.id}'
        tenant_slug = base
        i = 2
        while Tenant.objects.filter(slug=tenant_slug).exists():
            tenant_slug = f'{base}-{i}'
            i += 1
        tenant = Tenant.objects.create(name=f"{user.username}'s Workspace", slug=tenant_slug)
        membership = TenantMembership.objects.create(tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER)
        memberships = [membership]
    else:
        memberships = list(memberships)

    tenant = memberships[0].tenant
    workspace = tenant.workspaces.order_by('created_at').first()
    if workspace is None:
        workspace = Workspace.objects.create(tenant=tenant, name='Default Workspace', slug='default')

    session['current_tenant_id'] = tenant.id
    session['current_workspace_id'] = workspace.id
    return tenant, workspace


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        _bootstrap_user_workspace(user, request.session)
        login(request, user)
        return redirect('dashboard')
    return render(request, 'auth/signup.html', {'form': form})


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')

    if not request.session.get('current_tenant_id') or not request.session.get('current_workspace_id'):
        _bootstrap_user_workspace(request.user, request.session)

    memberships = TenantMembership.objects.select_related('tenant').filter(user=request.user)
    current_tenant_id = request.session.get('current_tenant_id')
    current_workspace_id = request.session.get('current_workspace_id')
    current_workspace = None
    documents = Document.objects.none()

    if current_tenant_id and current_workspace_id:
        current_workspace = Workspace.objects.select_related('tenant').filter(
            id=current_workspace_id,
            tenant_id=current_tenant_id,
        ).first()
        if current_workspace:
            documents = Document.objects.filter(
                tenant_id=current_tenant_id,
                workspace_id=current_workspace_id,
            ).prefetch_related('ingestion_jobs', 'chunks', 'versions').order_by('-created_at')[:25]

    if request.method == 'POST' and request.POST.get('action') == 'create_workspace':
        name = (request.POST.get('workspace_name') or '').strip() or 'New Workspace'
        if current_tenant_id:
            tenant = Tenant.objects.get(id=current_tenant_id)
            base = slugify(name) or 'workspace'
            slug = base
            i = 2
            while Workspace.objects.filter(tenant=tenant, slug=slug).exists():
                slug = f'{base}-{i}'
                i += 1
            workspace = Workspace.objects.create(tenant=tenant, name=name, slug=slug)
            request.session['current_workspace_id'] = workspace.id
            messages.success(request, f'Workspace "{workspace.name}" created and selected.')
        return redirect('dashboard')

    if request.method == 'POST' and request.POST.get('action') == 'switch_workspace':
        workspace_id = request.POST.get('workspace_id')
        workspace = Workspace.objects.filter(id=workspace_id, tenant_id=current_tenant_id).first()
        if workspace:
            request.session['current_workspace_id'] = workspace.id
            messages.success(request, f'Switched to workspace "{workspace.name}".')
        return redirect('dashboard')

    if request.method == 'POST' and request.FILES.get('file') and current_workspace:
        upload = request.FILES['file']
        collection = (request.POST.get('collection') or '').strip()
        try:
            with transaction.atomic():
                document = Document.objects.create(
                    tenant=current_workspace.tenant,
                    workspace=current_workspace,
                    collection=collection,
                    filename=upload.name,
                    mime_type=getattr(upload, 'content_type', '') or '',
                    size_bytes=getattr(upload, 'size', 0) or 0,
                    object_key=f'{current_workspace.tenant.slug}/{current_workspace.slug}/{upload.name}',
                    source_type=Document.SOURCE_UPLOAD,
                    uploaded_by=request.user,
                    file=upload,
                )
                version = document.versions.create(
                    version_number=1,
                    object_key=document.object_key,
                    content_hash='',
                    extraction_metadata_json={},
                )
                job = IngestionJob.objects.create(
                    tenant=current_workspace.tenant,
                    workspace=current_workspace,
                    document=document,
                    document_version=version,
                    status=IngestionJob.STATUS_QUEUED,
                    stage='queued',
                )
            ingest_document_task.delay(job.id)
            messages.success(request, f'Uploaded {document.filename}. Ingestion job #{job.id} queued.')
        except Exception as exc:
            logger.exception('Dashboard upload failed for user=%s workspace=%s filename=%s', request.user.id, current_workspace.id, getattr(upload, 'name', ''))
            messages.error(request, f'Upload failed: {exc}')
        return redirect('dashboard')

    document_rows = []
    for document in documents:
        latest_job = document.ingestion_jobs.order_by('-created_at').first()
        latest_version = document.versions.order_by('-version_number', '-id').first()
        chunk_count = document.chunks.count()
        preview = ''
        if latest_version:
            preview = (latest_version.extraction_metadata_json or {}).get('raw_text_preview', '')
        document_rows.append({
            'document': document,
            'latest_job': latest_job,
            'chunk_count': chunk_count,
            'preview': preview,
        })

    available_workspaces = Workspace.objects.filter(tenant_id=current_tenant_id).order_by('name') if current_tenant_id else Workspace.objects.none()

    return render(
        request,
        'dashboard.html',
        {
            'memberships': memberships,
            'current_tenant_id': current_tenant_id,
            'current_workspace_id': current_workspace_id,
            'current_workspace': current_workspace,
            'available_workspaces': available_workspaces,
            'document_rows': document_rows,
        },
    )
