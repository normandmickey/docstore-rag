import logging
import secrets
import subprocess

import requests

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify

from connectors.google_drive import GoogleDriveClient
from connectors.models import Connector, ExternalDocumentBinding
from documents.models import Chunk, Document, DocumentWorkspaceAssignment, ExtractedFact
from documents.upload_service import collect_urls_for_ingest, create_or_reuse_document, create_or_reuse_url_document
from ingestion.models import IngestionJob
from ingestion.tasks import ingest_document_task
from retrieval.service import answer_question, build_context_blocks, retrieve_chunks
from providers import answer_with_general_context

from .forms import SignUpForm, TenantSettingsForm
from .models import APIKey, ExternalAccount, InviteToken, ProxiWebMessage, ProxiWebThread, Tenant, TenantMembership, Workspace
from .api_auth import hash_api_key
from .oauth import (
    exchange_code_for_tokens,
    exchange_google_code_for_tokens,
    fetch_google_userinfo,
    fetch_graph_me,
    google_authorize_url,
    microsoft_authorize_url,
    refresh_google_tokens,
)
from .pii import redact_pii
from .email_flows import send_invite_email

logger = logging.getLogger(__name__)
User = get_user_model()


def _get_valid_google_access_token(account):
    if not account:
        return ''
    if account.expires_at and account.expires_at > timezone.now() + timezone.timedelta(minutes=5) and account.access_token:
        return account.access_token
    if not account.refresh_token:
        return account.access_token
    tokens = refresh_google_tokens(account.refresh_token)
    account.access_token = tokens.get('access_token', account.access_token)
    if tokens.get('refresh_token'):
        account.refresh_token = tokens.get('refresh_token')
    account.expires_at = tokens.get('expires_at')
    account.save(update_fields=['access_token', 'refresh_token', 'expires_at', 'updated_at'])
    return account.access_token


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


def _apply_invite_membership(invite, user, session):
    tenant = invite.tenant
    if tenant is None:
        return _bootstrap_user_workspace(user, session)

    workspace = invite.workspace or tenant.workspaces.order_by('created_at').first()
    if workspace is None:
        workspace = Workspace.objects.create(tenant=tenant, name='Default Workspace', slug='default')

    TenantMembership.objects.update_or_create(
        tenant=tenant,
        user=user,
        defaults={'role': invite.role or TenantMembership.ROLE_MEMBER},
    )

    invite.claimed_by = user
    invite.claimed_at = timezone.now()
    invite.active = False
    invite.save(update_fields=['claimed_by', 'claimed_at', 'active', 'updated_at'])

    session['current_tenant_id'] = tenant.id
    session['current_workspace_id'] = workspace.id
    return tenant, workspace


def _dashboard_base(request):
    if not request.user.is_authenticated:
        return None

    if not request.session.get('current_tenant_id') or not request.session.get('current_workspace_id'):
        _bootstrap_user_workspace(request.user, request.session)

    memberships = TenantMembership.objects.select_related('tenant').filter(user=request.user)
    current_tenant_id = request.session.get('current_tenant_id')
    current_workspace_id = request.session.get('current_workspace_id')
    current_workspace = None
    documents = Document.objects.none()
    deleted_documents = Document.objects.none()

    current_tenant = Tenant.objects.filter(id=current_tenant_id).first() if current_tenant_id else None

    if current_tenant_id and current_workspace_id:
        current_workspace = Workspace.objects.select_related('tenant').filter(
            id=current_workspace_id,
            tenant_id=current_tenant_id,
        ).first()
        if current_workspace:
            documents = Document.objects.filter(
                tenant_id=current_tenant_id,
                workspace_assignments__workspace_id=current_workspace_id,
            ).exclude(
                status__in=[Document.STATUS_FAILED, Document.STATUS_DELETED],
            ).prefetch_related('ingestion_jobs', 'chunks', 'versions', 'workspace_assignments__workspace').distinct().order_by('-created_at')[:25]
            deleted_documents = Document.objects.filter(
                tenant_id=current_tenant_id,
                workspace_assignments__workspace_id=current_workspace_id,
                status=Document.STATUS_DELETED,
            ).prefetch_related('ingestion_jobs', 'chunks', 'versions', 'workspace_assignments__workspace').distinct().order_by('-updated_at')[:25]

    def build_document_rows(items):
        rows = []
        for document in items:
            latest_job = document.ingestion_jobs.order_by('-created_at').first()
            latest_version = document.versions.order_by('-version_number', '-id').first()
            version_count = document.versions.count()
            chunk_count = document.chunks.count()
            preview = ''
            if latest_version:
                preview = (latest_version.extraction_metadata_json or {}).get('raw_text_preview', '')
            rows.append({
                'document': document,
                'latest_job': latest_job,
                'latest_version': latest_version,
                'version_count': version_count,
                'chunk_count': chunk_count,
                'preview': preview,
                'source_url': document.source_url,
                'assigned_workspaces': [assignment.workspace for assignment in document.workspace_assignments.all()],
            })
        return rows

    all_document_rows = build_document_rows(documents)
    failed_documents = Document.objects.filter(
        tenant_id=current_tenant_id,
        workspace_id=current_workspace_id,
        status=Document.STATUS_FAILED,
    ).prefetch_related('ingestion_jobs', 'chunks', 'versions').order_by('-updated_at')[:25] if current_workspace else Document.objects.none()

    deleted_document_rows = build_document_rows(deleted_documents)
    failed_document_rows = build_document_rows(failed_documents)
    url_document_rows = [row for row in all_document_rows if row['document'].source_type == Document.SOURCE_URL]
    file_document_rows = [row for row in all_document_rows if row['document'].source_type != Document.SOURCE_URL]

    current_membership = memberships.filter(tenant_id=current_tenant_id).first() if current_tenant_id else None
    can_manage_tenant = bool(current_membership and current_membership.role in {TenantMembership.ROLE_OWNER, TenantMembership.ROLE_ADMIN})

    return {
        'memberships': memberships,
        'current_tenant_id': current_tenant_id,
        'current_tenant': current_tenant,
        'current_membership': current_membership,
        'can_manage_tenant': can_manage_tenant,
        'current_workspace_id': current_workspace_id,
        'current_workspace': current_workspace,
        'available_workspaces': Workspace.objects.filter(tenant_id=current_tenant_id).order_by('name') if current_tenant_id else Workspace.objects.none(),
        'document_rows': all_document_rows,
        'file_document_rows': file_document_rows,
        'url_document_rows': url_document_rows,
        'deleted_document_rows': deleted_document_rows,
        'failed_document_rows': failed_document_rows,
        'external_accounts': ExternalAccount.objects.filter(user=request.user).order_by('-updated_at'),
        'api_keys': APIKey.objects.filter(tenant_id=current_tenant_id).order_by('-created_at') if current_tenant_id else APIKey.objects.none(),
        'is_staff_user': bool(request.user.is_staff),
    }


def _handle_workspace_actions(request, base):
    current_tenant_id = base['current_tenant_id']
    current_workspace = base['current_workspace']

    if request.method == 'POST' and request.POST.get('action') == 'create_workspace':
        name = (request.POST.get('workspace_name') or '').strip() or 'New Workspace'
        if current_tenant_id:
            tenant = Tenant.objects.get(id=current_tenant_id)
            base_slug = slugify(name) or 'workspace'
            slug = base_slug
            i = 2
            while Workspace.objects.filter(tenant=tenant, slug=slug).exists():
                slug = f'{base_slug}-{i}'
                i += 1
            workspace = Workspace.objects.create(tenant=tenant, name=name, slug=slug)
            request.session['current_workspace_id'] = workspace.id
            messages.success(request, f'Workspace "{workspace.name}" created and selected.')
        return redirect(request.path)

    if request.method == 'POST' and request.POST.get('action') == 'switch_workspace':
        workspace_id = request.POST.get('workspace_id')
        workspace = Workspace.objects.filter(id=workspace_id, tenant_id=current_tenant_id).first()
        if workspace:
            request.session['current_workspace_id'] = workspace.id
            messages.success(request, f'Switched to workspace "{workspace.name}".')
        return redirect(request.path)

    if request.method == 'POST' and request.POST.get('action') == 'assign_documents_workspace' and current_workspace:
        document_ids = [doc_id for doc_id in request.POST.getlist('document_ids') if doc_id]
        workspace_id = (request.POST.get('workspace_id') or '').strip()
        target_workspace = Workspace.objects.filter(id=workspace_id, tenant=current_workspace.tenant).first() if workspace_id.isdigit() else None
        if not document_ids:
            messages.error(request, 'Select at least one document to assign.')
            return redirect(request.path)
        if not target_workspace:
            messages.error(request, 'Select a valid workspace for assignment.')
            return redirect(request.path)
        documents_to_assign = list(Document.objects.filter(
            id__in=document_ids,
            tenant=current_workspace.tenant,
            workspace_assignments__workspace=current_workspace,
        ).distinct())
        created = 0
        for document in documents_to_assign:
            _assignment, was_created = DocumentWorkspaceAssignment.objects.get_or_create(
                document=document,
                workspace=target_workspace,
                defaults={'is_primary': target_workspace.id == document.workspace_id},
            )
            if was_created:
                created += 1
        messages.success(request, f'Assigned {created} document(s) to workspace "{target_workspace.name}".')
        return redirect(request.path)

    if request.method == 'POST' and request.POST.get('action') == 'delete_document' and current_workspace:
        document_ids = request.POST.getlist('document_ids') or [request.POST.get('document_id')]
        confirm = (request.POST.get('confirm_delete') or '').strip().lower()
        document_ids = [doc_id for doc_id in document_ids if doc_id]
        if confirm != 'yes':
            messages.error(request, 'Delete not confirmed. Check the confirmation box to soft-delete documents.')
            return redirect(request.path)
        documents_to_delete = list(Document.objects.filter(
            id__in=document_ids,
            tenant=current_workspace.tenant,
            workspace_assignments__workspace=current_workspace,
        ).exclude(status=Document.STATUS_DELETED).distinct())
        if not documents_to_delete:
            messages.error(request, 'No matching documents found.')
            return redirect(request.path)
        for document in documents_to_delete:
            document.soft_delete()
        messages.success(request, f'Soft-deleted {len(documents_to_delete)} document(s).')
        return redirect(request.path)

    if request.method == 'POST' and request.POST.get('action') == 'restore_document' and current_workspace:
        document_ids = [doc_id for doc_id in request.POST.getlist('document_ids') if doc_id]
        documents_to_restore = list(Document.objects.filter(
            id__in=document_ids,
            tenant=current_workspace.tenant,
            workspace_assignments__workspace=current_workspace,
            status=Document.STATUS_DELETED,
        ).distinct())
        if not documents_to_restore:
            messages.error(request, 'No deleted documents selected for restore.')
            return redirect(request.path)
        for document in documents_to_restore:
            document.restore()
        messages.success(request, f'Restored {len(documents_to_restore)} document(s).')
        return redirect(request.path)

    if request.method == 'POST' and request.POST.get('action') == 'purge_document' and current_workspace:
        document_ids = [doc_id for doc_id in request.POST.getlist('document_ids') if doc_id]
        confirm = (request.POST.get('confirm_purge') or '').strip().lower()
        if confirm != 'purge':
            messages.error(request, 'Purge not confirmed. Type PURGE in the confirmation box.')
            return redirect(request.path)
        documents_to_purge = list(Document.objects.filter(
            id__in=document_ids,
            tenant=current_workspace.tenant,
            workspace_assignments__workspace=current_workspace,
            status=Document.STATUS_DELETED,
        ).distinct())
        if not documents_to_purge:
            messages.error(request, 'No deleted documents selected for purge.')
            return redirect(request.path)
        purged = 0
        for document in documents_to_purge:
            if document.file:
                document.file.delete(save=False)
            document.delete()
            purged += 1
        messages.success(request, f'Permanently purged {purged} document(s).')
        return redirect(request.path)

    return None


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    token_value = (request.GET.get('invite') or request.POST.get('invite') or '').strip()
    invite = None
    if token_value:
        invite = InviteToken.objects.filter(token=token_value, active=True).first()
        if not invite:
            messages.error(request, 'Invite link is invalid or already used.')
            return redirect('login')
        if invite.expires_at and invite.expires_at <= timezone.now():
            messages.error(request, 'This invite link has expired.')
            return redirect('login')

    if not settings.ALLOW_PUBLIC_SIGNUPS and not invite:
        messages.error(request, 'Docstore is invite only right now.')
        return redirect('login')

    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        if invite:
            _apply_invite_membership(invite, user, request.session)
        else:
            _bootstrap_user_workspace(user, request.session)
        login(request, user)
        return redirect('dashboard')
    return render(request, 'auth/signup.html', {'form': form, 'invite_token': token_value, 'invite': invite})


def microsoft_connect_start(request):
    if not request.user.is_authenticated:
        return redirect('login')
    state = secrets.token_urlsafe(24)
    request.session['ms_oauth_state'] = state
    return redirect(microsoft_authorize_url(state))


def microsoft_connect_callback(request):
    if not request.user.is_authenticated:
        return redirect('login')

    expected_state = request.session.get('ms_oauth_state')
    returned_state = request.GET.get('state')
    code = request.GET.get('code')
    error = request.GET.get('error')

    if error:
        messages.error(request, f'Microsoft connection failed: {error}')
        return redirect('dashboard_connectors')
    if not code or not expected_state or expected_state != returned_state:
        messages.error(request, 'Microsoft connection failed: invalid OAuth state or missing code.')
        return redirect('dashboard_connectors')

    try:
        tokens = exchange_code_for_tokens(code)
        profile = fetch_graph_me(tokens['access_token'])
        if not request.session.get('current_tenant_id') or not request.session.get('current_workspace_id'):
            tenant, workspace = _bootstrap_user_workspace(request.user, request.session)
        else:
            tenant = Tenant.objects.get(id=request.session['current_tenant_id'])
            workspace = Workspace.objects.get(id=request.session['current_workspace_id'], tenant=tenant)

        account, _created = ExternalAccount.objects.update_or_create(
            user=request.user,
            provider=ExternalAccount.PROVIDER_MICROSOFT,
            external_user_id=profile.get('id', ''),
            defaults={
                'tenant': tenant,
                'workspace': workspace,
                'email': profile.get('mail') or profile.get('userPrincipalName', ''),
                'display_name': profile.get('displayName', ''),
                'access_token': tokens.get('access_token', ''),
                'refresh_token': tokens.get('refresh_token', ''),
                'expires_at': tokens.get('expires_at'),
                'scopes_json': settings.MS_GRAPH_SCOPES,
                'metadata_json': profile,
            },
        )
        messages.success(request, f'Connected Microsoft account for {account.email or account.display_name or "your account"}.')
    except Exception as exc:
        logger.exception('Microsoft OAuth callback failed for user=%s', request.user.id)
        messages.error(request, f'Microsoft connection failed: {exc}')
    return redirect('dashboard_connectors')


def google_connect_start(request):
    if not request.user.is_authenticated:
        return redirect('login')
    state = secrets.token_urlsafe(24)
    request.session['google_oauth_state'] = state
    return redirect(google_authorize_url(state))


def google_connect_callback(request):
    if not request.user.is_authenticated:
        return redirect('login')

    expected_state = request.session.get('google_oauth_state')
    returned_state = request.GET.get('state')
    code = request.GET.get('code')
    error = request.GET.get('error')

    if error:
        messages.error(request, f'Google connection failed: {error}')
        return redirect('dashboard_connectors')
    if not code or not expected_state or expected_state != returned_state:
        messages.error(request, 'Google connection failed: invalid OAuth state or missing code.')
        return redirect('dashboard_connectors')

    try:
        tokens = exchange_google_code_for_tokens(code)
        profile = fetch_google_userinfo(tokens['access_token'])
        if not request.session.get('current_tenant_id') or not request.session.get('current_workspace_id'):
            tenant, workspace = _bootstrap_user_workspace(request.user, request.session)
        else:
            tenant = Tenant.objects.get(id=request.session['current_tenant_id'])
            workspace = Workspace.objects.get(id=request.session['current_workspace_id'], tenant=tenant)

        account, _created = ExternalAccount.objects.update_or_create(
            user=request.user,
            provider=ExternalAccount.PROVIDER_GOOGLE,
            external_user_id=profile.get('sub', ''),
            defaults={
                'tenant': tenant,
                'workspace': workspace,
                'email': profile.get('email', ''),
                'display_name': profile.get('name', ''),
                'access_token': tokens.get('access_token', ''),
                'refresh_token': tokens.get('refresh_token', ''),
                'expires_at': tokens.get('expires_at'),
                'scopes_json': settings.GOOGLE_SCOPES,
                'metadata_json': profile,
            },
        )
        messages.success(request, f'Connected Google account for {account.email or account.display_name or "your account"}.')
    except Exception as exc:
        logger.exception('Google OAuth callback failed for user=%s', request.user.id)
        messages.error(request, f'Google connection failed: {exc}')
    return redirect('dashboard_connectors')


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled
    base['section'] = 'overview'
    base['recent_count'] = len(base['document_rows'])
    base['file_count'] = len(base['file_document_rows'])
    base['url_count'] = len(base['url_document_rows'])
    base['trash_count'] = len(base['deleted_document_rows'])
    return render(request, 'dashboard/index.html', base)


def document_download(request, document_id):
    if not request.user.is_authenticated:
        return redirect('login')

    document = get_object_or_404(Document, id=document_id)
    membership = TenantMembership.objects.filter(user=request.user, tenant=document.tenant).exists()
    if not membership and not request.user.is_staff:
        raise Http404('Document not found.')
    if not document.file:
        raise Http404('Document file not found.')

    try:
        fh = document.file.open('rb')
    except Exception as exc:
        raise Http404(f'Document file could not be opened: {exc}')

    response = FileResponse(fh, as_attachment=False, filename=document.filename)
    if document.mime_type:
        response['Content-Type'] = document.mime_type
    return response


def _document_detail_base(request, document_id):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled, None, None

    document = get_object_or_404(Document.objects.select_related('tenant', 'workspace').prefetch_related('workspace_assignments__workspace'), id=document_id)
    membership = TenantMembership.objects.filter(user=request.user, tenant=document.tenant).exists()
    if not membership and not request.user.is_staff:
        raise Http404('Document not found.')

    latest_version = document.versions.order_by('-version_number', '-id').first()
    latest_job = document.ingestion_jobs.order_by('-created_at').first()
    base.update({
        'section': 'documents',
        'detail_document': document,
        'detail_latest_version': latest_version,
        'detail_latest_job': latest_job,
        'detail_fact_count': ExtractedFact.objects.filter(document=document).count(),
        'detail_chunk_count': Chunk.objects.filter(document=document).count(),
        'detail_workspace_assignments': document.workspace_assignments.all(),
        'detail_available_workspaces': Workspace.objects.filter(tenant=document.tenant).order_by('name'),
    })
    return None, base, document


def document_detail(request, document_id):
    if not request.user.is_authenticated:
        return redirect('login')

    handled, base, document = _document_detail_base(request, document_id)
    if handled:
        return handled

    if request.method == 'POST' and request.POST.get('action') == 'assign_document_workspace':
        workspace_id = (request.POST.get('workspace_id') or '').strip()
        workspace = Workspace.objects.filter(id=workspace_id, tenant=document.tenant).first() if workspace_id.isdigit() else None
        if not workspace:
            messages.error(request, 'Select a valid workspace to assign.')
            return redirect(request.path)
        assignment, created = DocumentWorkspaceAssignment.objects.get_or_create(
            document=document,
            workspace=workspace,
            defaults={'is_primary': workspace.id == document.workspace_id},
        )
        if created:
            messages.success(request, f'Assigned document to workspace "{workspace.name}".')
        else:
            messages.info(request, f'Document is already assigned to workspace "{workspace.name}".')
        return redirect(request.path)

    if request.method == 'POST' and request.POST.get('action') == 'unassign_document_workspace':
        workspace_id = (request.POST.get('workspace_id') or '').strip()
        assignment = DocumentWorkspaceAssignment.objects.filter(
            document=document,
            workspace_id=workspace_id,
        ).select_related('workspace').first() if workspace_id.isdigit() else None
        if not assignment:
            messages.error(request, 'Workspace assignment not found.')
            return redirect(request.path)
        assignment_count = DocumentWorkspaceAssignment.objects.filter(document=document).count()
        if assignment.is_primary or assignment.workspace_id == document.workspace_id:
            messages.error(request, 'You cannot remove the primary workspace assignment from this screen.')
            return redirect(request.path)
        if assignment_count <= 1:
            messages.error(request, 'A document must remain assigned to at least one workspace.')
            return redirect(request.path)
        workspace_name = assignment.workspace.name
        assignment.delete()
        messages.success(request, f'Removed workspace assignment "{workspace_name}".')
        return redirect(request.path)

    if request.method == 'POST' and request.POST.get('action') == 'reingest_document':
        extractor = (request.POST.get('extractor') or IngestionJob.EXTRACTOR_STANDARD).strip()
        if extractor not in {IngestionJob.EXTRACTOR_STANDARD, IngestionJob.EXTRACTOR_DOCLING}:
            extractor = IngestionJob.EXTRACTOR_STANDARD
        version = document.versions.order_by('-version_number', '-id').first()
        if not version:
            messages.error(request, 'No document version available to reingest.')
            return redirect(request.path)
        job = IngestionJob.objects.create(
            tenant=document.tenant,
            workspace=document.workspace,
            document=document,
            document_version=version,
            extractor=extractor,
            status=IngestionJob.STATUS_QUEUED,
            stage='queued',
        )
        ingest_document_task.delay(job.id)
        messages.success(request, f'Reingest queued using extractor: {extractor}.')
        return redirect(request.path)

    base['detail_section'] = 'overview'
    return render(request, 'dashboard/document_detail.html', base)


def document_facts(request, document_id):
    if not request.user.is_authenticated:
        return redirect('login')

    handled, base, document = _document_detail_base(request, document_id)
    if handled:
        return handled

    fact_type = (request.GET.get('fact_type') or '').strip()
    facts = ExtractedFact.objects.filter(document=document).select_related('chunk').order_by('-confidence', 'id')
    if fact_type in {ExtractedFact.FACT_HEADING, ExtractedFact.FACT_LIST_ITEM, ExtractedFact.FACT_POLICY}:
        facts = facts.filter(fact_type=fact_type)
    paginator = Paginator(facts, 50)
    page_obj = paginator.get_page(request.GET.get('page'))

    base.update({
        'detail_section': 'facts',
        'page_obj': page_obj,
        'fact_type_filter': fact_type,
        'fact_type_options': [
            ('', 'All'),
            (ExtractedFact.FACT_HEADING, 'Heading'),
            (ExtractedFact.FACT_LIST_ITEM, 'List item'),
            (ExtractedFact.FACT_POLICY, 'Policy'),
        ],
    })
    return render(request, 'dashboard/document_facts.html', base)


def document_chunks(request, document_id):
    if not request.user.is_authenticated:
        return redirect('login')

    handled, base, document = _document_detail_base(request, document_id)
    if handled:
        return handled

    chunks = Chunk.objects.filter(document=document).order_by('chunk_index')
    paginator = Paginator(chunks, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    base.update({
        'detail_section': 'chunks',
        'page_obj': page_obj,
    })
    return render(request, 'dashboard/document_chunks.html', base)


def document_search(request, document_id):
    if not request.user.is_authenticated:
        return redirect('login')

    handled, base, document = _document_detail_base(request, document_id)
    if handled:
        return handled

    query = (request.GET.get('q') or '').strip()
    results = []
    if query:
        results = retrieve_chunks(
            tenant=document.tenant,
            workspace=document.workspace,
            query=query,
            top_k=12,
            document_id=document.id,
        )

    base.update({
        'detail_section': 'search',
        'search_query': query,
        'search_results': results,
    })
    return render(request, 'dashboard/document_search.html', base)


def dashboard_documents(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    current_workspace = base['current_workspace']
    uploads = request.FILES.getlist('file') if request.method == 'POST' else []
    if request.method == 'POST' and uploads and current_workspace:
        collection = (request.POST.get('collection') or '').strip()
        created = 0
        versioned = 0
        duplicates = 0
        failed = []
        for upload in uploads:
            try:
                result = create_or_reuse_document(
                    tenant=current_workspace.tenant,
                    workspace=current_workspace,
                    uploaded_file=upload,
                    filename=upload.name,
                    mime_type=getattr(upload, 'content_type', '') or '',
                    size_bytes=getattr(upload, 'size', 0) or 0,
                    collection=collection,
                    uploaded_by=request.user,
                    extractor=IngestionJob.EXTRACTOR_STANDARD,
                )
                if result['mode'] == 'duplicate':
                    duplicates += 1
                elif result['mode'] == 'versioned':
                    versioned += 1
                else:
                    created += 1
            except Exception as exc:
                logger.exception('Dashboard upload failed for user=%s workspace=%s filename=%s', request.user.id, current_workspace.id, getattr(upload, 'name', ''))
                failed.append(f"{getattr(upload, 'name', 'file')} ({exc})")

        summary = f'Upload summary: created {created}, versioned {versioned}, skipped duplicates {duplicates}'
        if failed:
            messages.error(request, summary + f", failed {len(failed)}. Failed files: " + '; '.join(failed[:5]))
        else:
            messages.success(request, summary + '.')
        return redirect('dashboard_documents')

    base['section'] = 'documents'
    return render(request, 'dashboard/documents.html', base)


def dashboard_urls(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    current_workspace = base['current_workspace']
    base['url_ingest_summary'] = ''
    if request.method == 'POST' and request.POST.get('action') == 'ingest_urls' and current_workspace:
        raw_urls = request.POST.get('urls') or ''
        collection = (request.POST.get('collection') or '').strip()
        crawl_mode = (request.POST.get('crawl_mode') or 'single').strip()
        max_pages_raw = (request.POST.get('max_pages') or '10').strip()
        try:
            max_pages = max(1, min(int(max_pages_raw or '10'), 50))
        except ValueError:
            max_pages = 10
        seed_urls = [line.strip() for line in raw_urls.splitlines() if line.strip()]
        created = 0
        versioned = 0
        skipped = 0
        failed = []
        if not seed_urls:
            messages.error(request, 'Add at least one URL.')
            return redirect('dashboard_urls')
        valid_seeds = []
        for url in seed_urls:
            if not (url.startswith('http://') or url.startswith('https://')):
                failed.append(f'{url} (invalid URL)')
            else:
                valid_seeds.append(url)
        urls = collect_urls_for_ingest(valid_seeds, crawl_mode=crawl_mode, max_pages=max_pages)
        existing_url_set = set(Document.objects.filter(
            tenant=current_workspace.tenant,
            workspace=current_workspace,
            source_type=Document.SOURCE_URL,
            source_url__in=urls,
        ).values_list('source_url', flat=True))
        known_skips = 0
        for url in urls:
            if url in existing_url_set:
                skipped += 1
                known_skips += 1
                continue
            try:
                result = create_or_reuse_url_document(
                    tenant=current_workspace.tenant,
                    workspace=current_workspace,
                    url=url,
                    collection=collection,
                    uploaded_by=request.user,
                )
                if result['mode'] == 'duplicate':
                    skipped += 1
                elif result['mode'] == 'versioned':
                    versioned += 1
                else:
                    created += 1
            except Exception as exc:
                logger.exception('Dashboard URL ingest failed for user=%s workspace=%s url=%s', request.user.id, current_workspace.id, url)
                failed.append(f'{url} ({exc})')
        summary = f'URL ingest: scanned {len(urls)} URLs, created {created}, versioned {versioned}, skipped {skipped}'
        if known_skips:
            summary += f' ({known_skips} already known source URLs)'
        base['url_ingest_summary'] = summary
        if failed:
            summary += f', failed {len(failed)}.'
            messages.error(request, summary + ' Failed URLs: ' + '; '.join(failed[:5]))
        else:
            messages.success(request, summary + '.')
        return redirect('dashboard_urls')

    base['section'] = 'urls'
    return render(request, 'dashboard/urls.html', base)


def dashboard_chat(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    current_workspace = base['current_workspace']
    base['chat_answer'] = ''
    base['chat_question'] = ''
    base['chat_results'] = []
    base['chat_contains_pii'] = False
    base['chat_pii_types'] = []
    if request.method == 'POST' and request.POST.get('action') == 'ask_question' and current_workspace:
        raw_chat_question = (request.POST.get('question') or '').strip()
        redacted_chat_question = redact_pii(raw_chat_question)
        chat_question = redacted_chat_question['text']
        selected_document_id = (request.POST.get('document_id') or '').strip()
        document_scope = int(selected_document_id) if selected_document_id.isdigit() else None
        base['chat_question'] = chat_question
        if chat_question:
            try:
                chat_answer, chat_results = answer_question(
                    tenant=current_workspace.tenant,
                    workspace=current_workspace,
                    query=chat_question,
                    top_k=5,
                    document_id=document_scope,
                )
                redacted_chat_answer = redact_pii(chat_answer)
                base['chat_answer'] = redacted_chat_answer['text']
                base['chat_results'] = chat_results
                base['chat_contains_pii'] = redacted_chat_answer['contains_pii'] or redacted_chat_question['contains_pii']
                base['chat_pii_types'] = sorted(set(redacted_chat_question['pii_types'] + redacted_chat_answer['pii_types']))
            except Exception as exc:
                logger.exception('Dashboard chat failed for user=%s workspace=%s', request.user.id, current_workspace.id)
                messages.error(request, f'Chat failed: {exc}')
        else:
            messages.error(request, 'Ask a question first.')
    base['section'] = 'chat'
    return render(request, 'dashboard/chat.html', base)


def dashboard_proxi_web(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    current_workspace = base['current_workspace']
    base['section'] = 'proxi_web'
    base['proxi_threads'] = ProxiWebThread.objects.none()
    base['proxi_thread'] = None
    base['proxi_messages'] = []
    base['proxi_question'] = ''
    base['proxi_results'] = []
    base['proxi_web_enabled'] = False

    if current_workspace:
        threads = ProxiWebThread.objects.filter(
            tenant=current_workspace.tenant,
            workspace=current_workspace,
            user=request.user,
        ).order_by('-updated_at', '-id')
        base['proxi_threads'] = threads

        if request.method == 'POST' and request.POST.get('action') == 'create_proxi_thread':
            title = (request.POST.get('title') or '').strip() or 'New Proxi-Web chat'
            thread = ProxiWebThread.objects.create(
                tenant=current_workspace.tenant,
                workspace=current_workspace,
                user=request.user,
                title=title,
            )
            messages.success(request, 'Created a new Proxi-Web chat.')
            return redirect(f'/dashboard/proxi-web/?thread={thread.id}')

        if request.method == 'POST' and request.POST.get('action') == 'rename_proxi_thread':
            thread_id = (request.POST.get('thread_id') or '').strip()
            new_title = (request.POST.get('title') or '').strip()
            thread = threads.filter(id=thread_id).first() if thread_id.isdigit() else None
            if not thread:
                messages.error(request, 'Chat not found.')
                return redirect('dashboard_proxi_web')
            thread.title = new_title or thread.title or 'Untitled chat'
            thread.save(update_fields=['title', 'updated_at'])
            messages.success(request, 'Chat renamed.')
            return redirect(f'/dashboard/proxi-web/?thread={thread.id}')

        if request.method == 'POST' and request.POST.get('action') == 'delete_proxi_thread':
            thread_id = (request.POST.get('thread_id') or '').strip()
            confirm = (request.POST.get('confirm_delete_thread') or '').strip().lower()
            thread = threads.filter(id=thread_id).first() if thread_id.isdigit() else None
            if not thread:
                messages.error(request, 'Chat not found.')
                return redirect('dashboard_proxi_web')
            if confirm != 'delete':
                messages.error(request, 'Delete not confirmed. Type DELETE to remove the chat.')
                return redirect(f'/dashboard/proxi-web/?thread={thread.id}')
            thread.delete()
            messages.success(request, 'Proxi-Web chat deleted.')
            return redirect('dashboard_proxi_web')

        selected_thread_id = (request.GET.get('thread') or request.POST.get('thread_id') or '').strip()
        thread = None
        if selected_thread_id.isdigit():
            thread = threads.filter(id=int(selected_thread_id)).first()
        if thread is None:
            thread = threads.first()
        base['proxi_thread'] = thread

        if request.method == 'POST' and request.POST.get('action') == 'send_proxi_message':
            raw_question = (request.POST.get('question') or '').strip()
            thread_id = (request.POST.get('thread_id') or '').strip()
            use_web = (request.POST.get('use_web_search') or '').strip() == '1'
            thread = threads.filter(id=thread_id).first() if thread_id.isdigit() else thread
            if not thread:
                messages.error(request, 'Pick or create a Proxi-Web chat first.')
                return redirect('dashboard_proxi_web')
            redacted_question = redact_pii(raw_question)
            question = redacted_question['text']
            base['proxi_thread'] = thread
            base['proxi_question'] = question
            base['proxi_web_enabled'] = use_web
            if not question:
                messages.error(request, 'Ask something first.')
            else:
                history_messages = list(thread.messages.order_by('id'))
                chat_history = [
                    {'role': message.role, 'content': message.content}
                    for message in history_messages[-12:]
                ]
                retrieval_results = retrieve_chunks(
                    tenant=current_workspace.tenant,
                    workspace=current_workspace,
                    query=question,
                    top_k=5,
                )
                context_blocks = build_context_blocks(retrieval_results)
                web_results = []
                if use_web:
                    if not getattr(settings, 'BRAVE_API_KEY', ''):
                        messages.error(request, 'Web search is not configured yet.')
                    else:
                        try:
                            response = requests.get(
                                'https://api.search.brave.com/res/v1/web/search',
                                params={'q': question, 'count': 5},
                                headers={
                                    'Accept': 'application/json',
                                    'Accept-Encoding': 'gzip',
                                    'X-Subscription-Token': settings.BRAVE_API_KEY,
                                },
                                timeout=20,
                            )
                            response.raise_for_status()
                            payload = response.json() or {}
                            for item in ((payload.get('web') or {}).get('results') or [])[:5]:
                                web_results.append({
                                    'title': item.get('title', ''),
                                    'url': item.get('url', ''),
                                    'snippet': item.get('description', ''),
                                })
                        except Exception as exc:
                            logger.exception('Proxi-Web web search failed for user=%s workspace=%s', request.user.id, current_workspace.id)
                            messages.error(request, f'Web search failed: {exc}')
                for index, item in enumerate(web_results, start=1):
                    context_blocks.append(
                        'UNTRUSTED WEB RESULT\n'
                        f'[Web {index}] {item.get("title") or item.get("url") or "Web result"}\n'
                        f'URL: {item.get("url", "")}\n'
                        f'{item.get("snippet", "")}'
                    )
                answer = answer_with_general_context(
                    question,
                    context_blocks,
                    chat_history=chat_history,
                ) if context_blocks else 'I could not find enough relevant context for that question yet.'
                redacted_answer = redact_pii(answer)
                ProxiWebMessage.objects.create(
                    thread=thread,
                    role=ProxiWebMessage.ROLE_USER,
                    content=redacted_question['text'],
                    retrieval_metadata_json={
                        'contains_pii': redacted_question['contains_pii'],
                        'pii_types': redacted_question['pii_types'],
                        'redacted_preview': redacted_question['text'][:500],
                    },
                )
                ProxiWebMessage.objects.create(
                    thread=thread,
                    role=ProxiWebMessage.ROLE_ASSISTANT,
                    content=redacted_answer['text'],
                    retrieval_metadata_json={
                        'use_web_search': use_web,
                        'contains_pii': redacted_answer['contains_pii'],
                        'pii_types': redacted_answer['pii_types'],
                        'redacted_preview': redacted_answer['text'][:500],
                        'result_count': len(retrieval_results),
                        'results': [
                            {
                                'document_id': result.document_id,
                                'document': result.document.filename,
                                'chunk_index': result.chunk_index,
                                'distance': float(getattr(result, 'distance', 0.0) or 0.0),
                                'detail_url': f'/documents/{result.document_id}/',
                                'download_url': f'/documents/{result.document_id}/download/',
                            }
                            for result in retrieval_results
                        ],
                        'web_results': web_results,
                    },
                )
                if (thread.title or '').strip() in {'', 'New Proxi-Web chat'}:
                    thread.title = (question[:80] or 'New Proxi-Web chat').strip()
                thread.save(update_fields=['title', 'updated_at'])
                messages.success(request, 'Message added to Proxi-Web chat.')
                return redirect(f'/dashboard/proxi-web/?thread={thread.id}')

        if base['proxi_thread']:
            chronological_messages = list(base['proxi_thread'].messages.order_by('id'))
            base['proxi_messages'] = list(reversed(chronological_messages))
            latest_assistant = next((msg for msg in reversed(chronological_messages) if msg.role == ProxiWebMessage.ROLE_ASSISTANT), None)
            if latest_assistant:
                latest_meta = latest_assistant.retrieval_metadata_json or {}
                base['proxi_results'] = latest_meta.get('results', [])
                base['proxi_web_results'] = latest_meta.get('web_results', [])
                base['proxi_web_enabled'] = bool(latest_meta.get('use_web_search'))

    return render(request, 'dashboard/proxi_web.html', base)


def dashboard_connectors(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    current_workspace = base['current_workspace']
    current_tenant = base['current_tenant']
    google_account = ExternalAccount.objects.filter(
        user=request.user,
        provider=ExternalAccount.PROVIDER_GOOGLE,
    ).order_by('-updated_at').first()
    base['google_account'] = google_account
    base['google_drive_files'] = []
    base['google_drive_query'] = ''
    base['google_drive_connector'] = None
    base['google_drive_folders'] = []
    base['google_drive_folder_parent_id'] = ''
    base['google_drive_folder_current_id'] = 'root'
    base['google_drive_folder_current_name'] = 'My Drive'

    if current_workspace and current_tenant:
        base['google_drive_connector'] = Connector.objects.filter(
            tenant=current_tenant,
            workspace=current_workspace,
            provider=Connector.PROVIDER_GOOGLE_DRIVE,
        ).order_by('-updated_at').first()

    if request.method == 'POST' and request.POST.get('action') == 'save_google_drive_connector' and current_workspace and current_tenant:
        if not google_account:
            messages.error(request, 'Connect a Google account first.')
            return redirect('dashboard_connectors')
        folder_id = (request.POST.get('folder_id') or 'root').strip() or 'root'
        label = (request.POST.get('label') or '').strip() or 'Google Drive'
        recursive = (request.POST.get('recursive') or '1').strip() == '1'
        sync_enabled = request.POST.get('sync_enabled') == '1'
        try:
            sync_frequency_minutes = int(request.POST.get('sync_frequency_minutes') or 60)
        except ValueError:
            sync_frequency_minutes = 60
        sync_frequency_minutes = max(15, sync_frequency_minutes)
        connector, _created = Connector.objects.update_or_create(
            tenant=current_tenant,
            workspace=current_workspace,
            provider=Connector.PROVIDER_GOOGLE_DRIVE,
            defaults={
                'label': label,
                'status': Connector.STATUS_ACTIVE,
                'config_json': {
                    'external_account_id': google_account.id,
                    'account_email': google_account.email,
                    'folder_id': folder_id,
                    'recursive': recursive,
                },
                'sync_enabled': sync_enabled,
                'sync_frequency_minutes': sync_frequency_minutes,
                'next_sync_at': timezone.now() + timezone.timedelta(minutes=sync_frequency_minutes) if sync_enabled else None,
            },
        )
        messages.success(request, f'Saved Google Drive connector for folder id: {folder_id}.')
        return redirect('dashboard_connectors')

    if request.method == 'POST' and request.POST.get('action') == 'sync_google_drive_connector' and current_workspace and current_tenant:
        connector = Connector.objects.filter(
            tenant=current_tenant,
            workspace=current_workspace,
            provider=Connector.PROVIDER_GOOGLE_DRIVE,
        ).order_by('-updated_at').first()
        if not connector:
            messages.error(request, 'Save a Google Drive connector first.')
            return redirect('dashboard_connectors')
        try:
            result = subprocess.run(
                ['.venv/bin/python', 'manage.py', 'sync_google_drive_connector', str(connector.id)],
                cwd=str(settings.BASE_DIR),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode == 0:
                messages.success(request, result.stdout.strip() or 'Google Drive sync completed.')
            else:
                messages.error(request, result.stderr.strip() or result.stdout.strip() or 'Google Drive sync failed.')
        except Exception as exc:
            logger.exception('Google Drive sync command failed for connector=%s', connector.id)
            messages.error(request, f'Google Drive sync failed: {exc}')
        return redirect('dashboard_connectors')

    if request.method == 'POST' and request.POST.get('action') == 'use_google_drive_folder' and current_workspace and current_tenant:
        if not google_account:
            messages.error(request, 'Connect a Google account first.')
            return redirect('dashboard_connectors')
        folder_id = (request.POST.get('folder_id') or 'root').strip() or 'root'
        folder_name = (request.POST.get('folder_name') or '').strip() or 'Google Drive'
        connector, _created = Connector.objects.update_or_create(
            tenant=current_tenant,
            workspace=current_workspace,
            provider=Connector.PROVIDER_GOOGLE_DRIVE,
            defaults={
                'label': f'Google Drive · {folder_name}',
                'status': Connector.STATUS_ACTIVE,
                'config_json': {
                    'external_account_id': google_account.id,
                    'account_email': google_account.email,
                    'folder_id': folder_id,
                    'recursive': True,
                },
                'sync_enabled': False,
                'sync_frequency_minutes': 60,
                'next_sync_at': None,
            },
        )
        messages.success(request, f'Now using Google Drive folder "{folder_name}" for this workspace connector.')
        return redirect(f'/dashboard/connectors/?google_folder={folder_id}')

    if request.method == 'POST' and request.POST.get('action') == 'sync_google_drive_folder_now' and current_workspace and current_tenant:
        if not google_account:
            messages.error(request, 'Connect a Google account first.')
            return redirect('dashboard_connectors')
        folder_id = (request.POST.get('folder_id') or 'root').strip() or 'root'
        folder_name = (request.POST.get('folder_name') or '').strip() or 'Google Drive'
        connector, _created = Connector.objects.update_or_create(
            tenant=current_tenant,
            workspace=current_workspace,
            provider=Connector.PROVIDER_GOOGLE_DRIVE,
            defaults={
                'label': f'Google Drive · {folder_name}',
                'status': Connector.STATUS_ACTIVE,
                'config_json': {
                    'external_account_id': google_account.id,
                    'account_email': google_account.email,
                    'folder_id': folder_id,
                    'recursive': True,
                },
            },
        )
        try:
            result = subprocess.run(
                ['.venv/bin/python', 'manage.py', 'sync_google_drive_connector', str(connector.id)],
                cwd=str(settings.BASE_DIR),
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode == 0:
                messages.success(request, result.stdout.strip() or 'Google Drive sync completed.')
            else:
                messages.error(request, result.stderr.strip() or result.stdout.strip() or 'Google Drive sync failed.')
        except Exception as exc:
            logger.exception('Google Drive folder sync command failed for connector=%s', connector.id)
            messages.error(request, f'Google Drive sync failed: {exc}')
        return redirect(f'/dashboard/connectors/?google_folder={folder_id}')

    if request.method == 'POST' and request.POST.get('action') == 'google_drive_import' and current_workspace and current_tenant:
        if not google_account:
            messages.error(request, 'Connect a Google account first.')
            return redirect('dashboard_connectors')

        file_id = (request.POST.get('file_id') or '').strip()
        if not file_id:
            messages.error(request, 'Pick a Google Drive file to import.')
            return redirect('dashboard_connectors')

        try:
            client = GoogleDriveClient(_get_valid_google_access_token(google_account))
            remote = client.get_file(file_id)
            raw_bytes, import_mime, import_filename = client.download_file_bytes(
                file_id=file_id,
                mime_type=remote.get('mimeType', ''),
                filename=remote.get('name', '') or 'google-drive-file',
            )
            upload = ContentFile(raw_bytes, name=import_filename or remote.get('name') or 'google-drive-file')
            connector, _ = Connector.objects.get_or_create(
                tenant=current_tenant,
                workspace=current_workspace,
                provider=Connector.PROVIDER_GOOGLE_DRIVE,
                label='Google Drive',
                defaults={
                    'status': Connector.STATUS_ACTIVE,
                    'config_json': {
                        'external_account_id': google_account.id,
                        'account_email': google_account.email,
                    },
                },
            )
            result = create_or_reuse_document(
                tenant=current_tenant,
                workspace=current_workspace,
                uploaded_file=upload,
                filename=import_filename or remote.get('name') or 'google-drive-file',
                mime_type=import_mime or remote.get('mimeType', ''),
                size_bytes=len(raw_bytes),
                collection='google-drive',
                uploaded_by=request.user,
                source_type=Document.SOURCE_CONNECTOR,
                source_url=remote.get('webViewLink', ''),
            )
            ExternalDocumentBinding.objects.update_or_create(
                connector=connector,
                external_id=remote.get('id', file_id),
                defaults={
                    'external_path': 'google-drive',
                    'etag': remote.get('md5Checksum', ''),
                    'document': result['document'],
                    'metadata_json': {
                        'name': remote.get('name', ''),
                        'mime_type': remote.get('mimeType', ''),
                        'modified_time': remote.get('modifiedTime', ''),
                        'web_url': remote.get('webViewLink', ''),
                    },
                },
            )
            messages.success(request, f'Imported Google Drive file: {remote.get("name") or import_filename}.')
            return redirect('dashboard_connectors')
        except Exception as exc:
            logger.exception('Google Drive import failed for user=%s workspace=%s file_id=%s', request.user.id, current_workspace.id, file_id)
            messages.error(request, f'Google Drive import failed: {exc}')
            return redirect('dashboard_connectors')

    if google_account:
        query = (request.GET.get('google_q') or '').strip()
        folder_current_id = (request.GET.get('google_folder') or '').strip() or 'root'
        base['google_drive_query'] = query
        base['google_drive_folder_current_id'] = folder_current_id
        try:
            client = GoogleDriveClient(_get_valid_google_access_token(google_account))
            q = None
            if query:
                escaped = query.replace("'", "\\'")
                q = f"name contains '{escaped}' and trashed = false"
            else:
                q = 'trashed = false'
            base['google_drive_files'] = client.list_files(q=q, page_size=20)

            current_folder = {'id': 'root', 'name': 'My Drive', 'parents': []}
            if folder_current_id != 'root':
                current_folder = client.get_file(folder_current_id)
            parents = current_folder.get('parents') or []
            base['google_drive_folder_parent_id'] = parents[0] if parents else ''
            base['google_drive_folder_current_name'] = current_folder.get('name') or 'My Drive'
            base['google_drive_folders'] = client.list_folders(folder_id=folder_current_id, page_size=100)
        except Exception as exc:
            logger.exception('Google Drive list failed for user=%s', request.user.id)
            messages.error(request, f'Google Drive browse failed: {exc}')

    base['section'] = 'connectors'
    return render(request, 'dashboard/connectors.html', base)


def dashboard_tenant_settings(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled
    if not base.get('current_tenant'):
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can update tenant settings.')
        return redirect('dashboard')

    tenant = base['current_tenant']
    if request.method == 'POST':
        form = TenantSettingsForm(request.POST, instance=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tenant settings updated.')
            return redirect('dashboard_tenant_settings')
    else:
        form = TenantSettingsForm(instance=tenant)

    base['tenant_settings_form'] = form
    base['section'] = 'tenant'
    return render(request, 'dashboard/tenant_settings.html', base)


def dashboard_api_keys(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    current_workspace = base['current_workspace']
    tenant_id = base['current_tenant_id']
    base['section'] = 'api_keys'
    base['new_api_key'] = ''

    if request.method == 'POST' and request.POST.get('action') == 'create_api_key' and tenant_id:
        label = (request.POST.get('label') or '').strip() or 'API Key'
        scope = (request.POST.get('scope') or 'workspace').strip()
        raw_key = f"ds_{secrets.token_urlsafe(32)}"
        key_prefix = raw_key[:12]
        key_hash = hash_api_key(raw_key)
        workspace = current_workspace if scope == 'workspace' else None
        scopes_json = ['workspace'] if workspace else ['tenant']
        api_key = APIKey.objects.create(
            tenant_id=tenant_id,
            workspace=workspace,
            label=label,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes_json=scopes_json,
            active=True,
        )
        if api_key.key_hash != hash_api_key(raw_key):
            logger.error('API key integrity check failed immediately after creation for key_id=%s', api_key.id)
            api_key.active = False
            api_key.save(update_fields=['active'])
            messages.error(request, 'API key creation failed integrity verification. Please try again.')
            return redirect('dashboard_api_keys')
        base['new_api_key'] = raw_key
        messages.success(request, 'API key created. Copy it now — it will only be shown once.')
        base = _dashboard_base(request)
        base['section'] = 'api_keys'
        base['new_api_key'] = raw_key
        return render(request, 'dashboard/api_keys.html', base)

    if request.method == 'POST' and request.POST.get('action') == 'revoke_api_key' and tenant_id:
        key_id = request.POST.get('key_id')
        confirm = (request.POST.get('confirm_revoke') or '').strip().lower()
        if confirm != 'revoke':
            messages.error(request, 'Revoke not confirmed. Type REVOKE to disable the key.')
            return redirect('dashboard_api_keys')
        key = APIKey.objects.filter(id=key_id, tenant_id=tenant_id).first()
        if not key:
            messages.error(request, 'API key not found.')
            return redirect('dashboard_api_keys')
        key.active = False
        key.save(update_fields=['active'])
        messages.success(request, f'Revoked API key "{key.label}".')
        return redirect('dashboard_api_keys')

    return render(request, 'dashboard/api_keys.html', base)


def staff_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if not request.user.is_staff:
        messages.error(request, 'Staff access required.')
        return redirect('dashboard')

    if request.method == 'POST' and request.POST.get('action') == 'create_invite':
        email = (request.POST.get('email') or '').strip()
        tenant_id = (request.POST.get('tenant_id') or '').strip()
        workspace_id = (request.POST.get('workspace_id') or '').strip()
        role = (request.POST.get('role') or TenantMembership.ROLE_MEMBER).strip()
        note = (request.POST.get('note') or '').strip()
        tenant = Tenant.objects.filter(id=tenant_id).first() if tenant_id else None
        workspace = Workspace.objects.filter(id=workspace_id, tenant=tenant).first() if tenant and workspace_id else None
        invite = InviteToken.objects.create(
            email=email,
            token=secrets.token_urlsafe(32),
            tenant=tenant,
            workspace=workspace,
            role=role if role in {TenantMembership.ROLE_OWNER, TenantMembership.ROLE_ADMIN, TenantMembership.ROLE_MEMBER} else TenantMembership.ROLE_MEMBER,
            note=note,
            created_by=request.user,
            active=True,
        )
        signup_url = request.build_absolute_uri(f'/signup/?invite={invite.token}')
        if email:
            try:
                send_invite_email(
                    to_email=email,
                    signup_url=signup_url,
                    tenant_name=getattr(tenant, 'name', ''),
                    workspace_name=getattr(workspace, 'name', ''),
                    role=invite.role,
                    note=note,
                    invited_by=getattr(request.user, 'username', '') or getattr(request.user, 'email', ''),
                )
                messages.success(request, f'Invite created and emailed to {email}. Invite link: {signup_url}')
            except Exception as exc:
                logger.exception('Invite email send failed for invite_id=%s email=%s', invite.id, email)
                messages.warning(request, f'Invite created for {email}, but email send failed: {exc}. Share this URL manually: {signup_url}')
        else:
            messages.success(request, f'Invite created for link-only access. Share this URL: {signup_url}')
        return redirect('staff_dashboard')

    if request.method == 'POST' and request.POST.get('action') == 'disable_invite':
        invite = get_object_or_404(InviteToken, id=request.POST.get('invite_id'))
        invite.active = False
        invite.save(update_fields=['active', 'updated_at'])
        messages.success(request, 'Invite disabled.')
        return redirect('staff_dashboard')

    stats = {
        'users_count': User.objects.count(),
        'tenants_count': Tenant.objects.count(),
        'workspaces_count': Workspace.objects.count(),
        'documents_count': Document.objects.count(),
        'api_keys_count': APIKey.objects.count(),
        'connectors_count': Connector.objects.count(),
        'active_invites_count': InviteToken.objects.filter(active=True, claimed_at__isnull=True).count(),
    }

    recent_users = User.objects.order_by('-date_joined')[:10]
    recent_invites = InviteToken.objects.select_related('tenant', 'workspace', 'created_by', 'claimed_by').order_by('-created_at')[:20]
    tenant_rows = Tenant.objects.annotate(
        member_count=Count('memberships', distinct=True),
        workspace_count=Count('workspaces', distinct=True),
        document_count=Count('documents', distinct=True),
    ).order_by('name')[:25]

    context = {
        'section': 'staff',
        'is_staff_user': True,
        'current_workspace': None,
        'available_workspaces': Workspace.objects.none(),
        'staff_stats': stats,
        'recent_users': recent_users,
        'recent_invites': recent_invites,
        'tenant_rows': tenant_rows,
        'tenants': Tenant.objects.order_by('name'),
        'role_choices': TenantMembership.ROLE_CHOICES,
    }
    return render(request, 'dashboard/staff.html', context)
