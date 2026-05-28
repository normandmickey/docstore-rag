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
from .models import ExternalAccount, Tenant, TenantMembership, Workspace
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
        return redirect('dashboard')
    if not code or not expected_state or expected_state != returned_state:
        messages.error(request, 'Microsoft connection failed: invalid OAuth state or missing code.')
        return redirect('dashboard')

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
    return redirect('dashboard')


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
    external_accounts = ExternalAccount.objects.filter(user=request.user).order_by('-updated_at')
    url_ingest_summary = ''
    chat_answer = ''
    chat_question = ''
    chat_results = []

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
                status=Document.STATUS_FAILED,
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

    if request.method == 'POST' and request.POST.get('action') == 'ask_question' and current_workspace:
        chat_question = (request.POST.get('question') or '').strip()
        selected_document_id = (request.POST.get('document_id') or '').strip()
        document_scope = int(selected_document_id) if selected_document_id.isdigit() else None
        if chat_question:
            try:
                chat_answer, chat_results = answer_question(
                    tenant=current_workspace.tenant,
                    workspace=current_workspace,
                    query=chat_question,
                    top_k=5,
                    document_id=document_scope,
                )
            except Exception as exc:
                logger.exception('Dashboard chat failed for user=%s workspace=%s', request.user.id, current_workspace.id)
                messages.error(request, f'Chat failed: {exc}')
        else:
            messages.error(request, 'Ask a question first.')

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
            return redirect('dashboard')
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
        url_ingest_summary = summary
        if failed:
            summary += f', failed {len(failed)}.'
            messages.error(request, summary + ' Failed URLs: ' + '; '.join(failed[:5]))
        else:
            messages.success(request, summary + '.')
        return redirect('dashboard')

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
        return redirect('dashboard')

    document_rows = []
    for document in documents:
        latest_job = document.ingestion_jobs.order_by('-created_at').first()
        latest_version = document.versions.order_by('-version_number', '-id').first()
        version_count = document.versions.count()
        chunk_count = document.chunks.count()
        preview = ''
        if latest_version:
            preview = (latest_version.extraction_metadata_json or {}).get('raw_text_preview', '')
        document_rows.append({
            'document': document,
            'latest_job': latest_job,
            'latest_version': latest_version,
            'version_count': version_count,
            'chunk_count': chunk_count,
            'preview': preview,
            'source_url': document.source_url,
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
            'external_accounts': external_accounts,
            'url_ingest_summary': url_ingest_summary,
            'chat_question': chat_question,
            'chat_answer': chat_answer,
            'chat_results': chat_results,
        },
    )
