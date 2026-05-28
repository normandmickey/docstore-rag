import logging
import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils.text import slugify

from documents.models import Document
from documents.upload_service import collect_urls_for_ingest, create_or_reuse_document, create_or_reuse_url_document
from retrieval.service import answer_question

from .forms import SignUpForm
from .models import APIKey, ExternalAccount, Tenant, TenantMembership, Workspace
from .api_auth import hash_api_key
from .oauth import exchange_code_for_tokens, fetch_graph_me, microsoft_authorize_url

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

    if current_tenant_id and current_workspace_id:
        current_workspace = Workspace.objects.select_related('tenant').filter(
            id=current_workspace_id,
            tenant_id=current_tenant_id,
        ).first()
        if current_workspace:
            documents = Document.objects.filter(
                tenant_id=current_tenant_id,
                workspace_id=current_workspace_id,
            ).exclude(
                status__in=[Document.STATUS_FAILED, Document.STATUS_DELETED],
            ).prefetch_related('ingestion_jobs', 'chunks', 'versions').order_by('-created_at')[:25]
            deleted_documents = Document.objects.filter(
                tenant_id=current_tenant_id,
                workspace_id=current_workspace_id,
                status=Document.STATUS_DELETED,
            ).prefetch_related('ingestion_jobs', 'chunks', 'versions').order_by('-updated_at')[:25]

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
            })
        return rows

    all_document_rows = build_document_rows(documents)
    deleted_document_rows = build_document_rows(deleted_documents)
    url_document_rows = [row for row in all_document_rows if row['document'].source_type == Document.SOURCE_URL]
    file_document_rows = [row for row in all_document_rows if row['document'].source_type != Document.SOURCE_URL]

    return {
        'memberships': memberships,
        'current_tenant_id': current_tenant_id,
        'current_workspace_id': current_workspace_id,
        'current_workspace': current_workspace,
        'available_workspaces': Workspace.objects.filter(tenant_id=current_tenant_id).order_by('name') if current_tenant_id else Workspace.objects.none(),
        'document_rows': all_document_rows,
        'file_document_rows': file_document_rows,
        'url_document_rows': url_document_rows,
        'deleted_document_rows': deleted_document_rows,
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
            workspace=current_workspace,
        ).exclude(status=Document.STATUS_DELETED))
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
            workspace=current_workspace,
            status=Document.STATUS_DELETED,
        ))
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
            workspace=current_workspace,
            status=Document.STATUS_DELETED,
        ))
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
    form = SignUpForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        _bootstrap_user_workspace(user, request.session)
        login(request, user)
        return redirect('dashboard')
    return render(request, 'auth/signup.html', {'form': form})


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


def dashboard_documents(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    current_workspace = base['current_workspace']
    if request.method == 'POST' and request.FILES.get('file') and current_workspace:
        upload = request.FILES['file']
        collection = (request.POST.get('collection') or '').strip()
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
            )
            document = result['document']
            job = result['job']
            if result['mode'] == 'duplicate':
                messages.info(request, f'{document.filename} is already in this workspace. Skipped duplicate upload.')
            elif result['mode'] == 'versioned':
                messages.success(request, f'Uploaded new version of {document.filename}. Ingestion job #{job.id} queued.')
            else:
                messages.success(request, f'Uploaded {document.filename}. Ingestion job #{job.id} queued.')
        except Exception as exc:
            logger.exception('Dashboard upload failed for user=%s workspace=%s filename=%s', request.user.id, current_workspace.id, getattr(upload, 'name', ''))
            messages.error(request, f'Upload failed: {exc}')
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
    if request.method == 'POST' and request.POST.get('action') == 'ask_question' and current_workspace:
        chat_question = (request.POST.get('question') or '').strip()
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
                base['chat_answer'] = chat_answer
                base['chat_results'] = chat_results
            except Exception as exc:
                logger.exception('Dashboard chat failed for user=%s workspace=%s', request.user.id, current_workspace.id)
                messages.error(request, f'Chat failed: {exc}')
        else:
            messages.error(request, 'Ask a question first.')
    base['section'] = 'chat'
    return render(request, 'dashboard/chat.html', base)


def dashboard_connectors(request):
    if not request.user.is_authenticated:
        return redirect('login')
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled
    base['section'] = 'connectors'
    return render(request, 'dashboard/connectors.html', base)


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
