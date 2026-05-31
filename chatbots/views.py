import json
import logging
import secrets

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from control.oauth import exchange_zoom_code_for_tokens, zoom_authorize_url
from control.views import _dashboard_base, _handle_workspace_actions

from .forms import ChatbotDefinitionForm, ChatbotEndpointBindingForm, ChatbotEndpointForm, ChatbotIntegrationForm
from .models import ChatbotBuild, ChatbotDefinition, ChatbotDeployment, ChatbotEndpoint, ChatbotEndpointBinding, ChatbotEventLog, ChatbotIntegration

logger = logging.getLogger(__name__)


@login_required
def chatbot_index(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        return redirect('dashboard')

    base.update({
        'section': 'chatbots',
        'chatbot_integrations': ChatbotIntegration.objects.filter(tenant=tenant).order_by('platform', 'name')[:50],
        'chatbot_definitions': ChatbotDefinition.objects.filter(tenant=tenant).order_by('name')[:50],
        'chatbot_endpoint_bindings': ChatbotEndpointBinding.objects.filter(bot_definition__tenant=tenant).select_related('bot_definition', 'endpoint', 'workspace_override').order_by('bot_definition__name', 'endpoint__display_name')[:50],
        'chatbot_deployments': ChatbotDeployment.objects.filter(bot_definition__tenant=tenant).select_related('bot_definition', 'build').order_by('-created_at')[:25],
        'chatbot_recent_builds': ChatbotBuild.objects.filter(bot_definition__tenant=tenant).select_related('bot_definition').order_by('-created_at')[:25],
        'chatbot_recent_events': ChatbotEventLog.objects.filter(tenant=tenant).select_related('integration', 'endpoint', 'bot_definition').order_by('-created_at')[:25],
    })
    return render(request, 'dashboard/chatbots.html', base)


@login_required
def chatbot_integration_new(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can manage chatbot integrations.')
        return redirect('chatbot_index')

    if request.method == 'POST':
        form = ChatbotIntegrationForm(request.POST)
        if form.is_valid():
            integration = form.save(commit=False)
            integration.tenant = tenant
            integration.save()
            if not integration.webhook_url and integration.runner_key:
                if integration.platform == ChatbotIntegration.PLATFORM_TELEGRAM:
                    integration.webhook_url = f'https://bots.docstore.oddsmith.net/webhooks/telegram/{integration.runner_key}'
                elif integration.platform == ChatbotIntegration.PLATFORM_ZOOM_CHAT:
                    integration.webhook_url = f'https://bots.docstore.oddsmith.net/webhooks/zoom-chat/{integration.runner_key}'
                else:
                    integration.webhook_url = ''
                integration.webhook_status = integration.webhook_status or 'pending'
                integration.save(update_fields=['webhook_url', 'webhook_status', 'updated_at'])
            messages.success(request, f'Chatbot integration created. Runner key: {integration.runner_key}')
            return redirect('chatbot_index')
    else:
        form = ChatbotIntegrationForm()

    base.update({
        'section': 'chatbots',
        'chatbot_subsection': 'integration_new',
        'chatbot_form': form,
        'chatbot_form_title': 'New chatbot integration',
        'chatbot_form_submit': 'Create integration',
        'chatbot_zoom_help': True,
        'chatbot_runner_key_preview': '(generated after save)',
    })
    return render(request, 'dashboard/chatbot_form.html', base)


@login_required
def chatbot_integration_edit(request, integration_id):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can manage chatbot integrations.')
        return redirect('chatbot_index')

    integration = get_object_or_404(ChatbotIntegration, id=integration_id, tenant=tenant)
    if request.method == 'POST':
        form = ChatbotIntegrationForm(request.POST, instance=integration)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.tenant = tenant
            updated.save()
            messages.success(request, 'Chatbot integration updated.')
            return redirect('chatbot_index')
    else:
        form = ChatbotIntegrationForm(instance=integration)

    base.update({
        'section': 'chatbots',
        'chatbot_subsection': 'integration_edit',
        'chatbot_form': form,
        'chatbot_form_title': f'Edit chatbot integration: {integration.name}',
        'chatbot_form_submit': 'Save integration',
        'chatbot_zoom_help': True,
        'chatbot_runner_key_preview': integration.runner_key or '(missing)',
    })
    return render(request, 'dashboard/chatbot_form.html', base)


@login_required
def chatbot_definition_new(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can manage chatbot definitions.')
        return redirect('chatbot_index')

    if request.method == 'POST':
        form = ChatbotDefinitionForm(request.POST, tenant=tenant)
        if form.is_valid():
            definition = form.save(commit=False)
            definition.tenant = tenant
            definition.save()
            messages.success(request, 'Chatbot definition created.')
            return redirect('chatbot_index')
    else:
        form = ChatbotDefinitionForm(tenant=tenant)

    base.update({
        'section': 'chatbots',
        'chatbot_subsection': 'definition_new',
        'chatbot_form': form,
        'chatbot_form_title': 'New chatbot definition',
        'chatbot_form_submit': 'Create definition',
    })
    return render(request, 'dashboard/chatbot_form.html', base)


@login_required
def chatbot_endpoint_new(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can manage chatbot endpoints.')
        return redirect('chatbot_index')

    if request.method == 'POST':
        form = ChatbotEndpointForm(request.POST, tenant=tenant)
        if form.is_valid():
            endpoint = form.save(commit=False)
            endpoint.tenant = tenant
            endpoint.save()
            messages.success(request, 'Chatbot endpoint created.')
            return redirect('chatbot_index')
    else:
        form = ChatbotEndpointForm(tenant=tenant)

    base.update({
        'section': 'chatbots',
        'chatbot_subsection': 'endpoint_new',
        'chatbot_form': form,
        'chatbot_form_title': 'New chatbot endpoint',
        'chatbot_form_submit': 'Create endpoint',
    })
    return render(request, 'dashboard/chatbot_form.html', base)


@login_required
def chatbot_binding_new(request):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can manage chatbot bindings.')
        return redirect('chatbot_index')

    if request.method == 'POST':
        form = ChatbotEndpointBindingForm(request.POST, tenant=tenant)
        if form.is_valid():
            form.save()
            messages.success(request, 'Chatbot endpoint binding created.')
            return redirect('chatbot_index')
    else:
        form = ChatbotEndpointBindingForm(tenant=tenant)

    base.update({
        'section': 'chatbots',
        'chatbot_subsection': 'binding_new',
        'chatbot_form': form,
        'chatbot_form_title': 'New chatbot endpoint binding',
        'chatbot_form_submit': 'Create binding',
    })
    return render(request, 'dashboard/chatbot_form.html', base)


@login_required
def chatbot_zoom_connect_start(request, integration_id):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')
    if not base.get('can_manage_tenant'):
        messages.error(request, 'Only tenant owners and admins can connect Zoom Chat integrations.')
        return redirect('chatbot_index')

    integration = get_object_or_404(ChatbotIntegration, id=integration_id, tenant=tenant, platform=ChatbotIntegration.PLATFORM_ZOOM_CHAT)
    nonce = secrets.token_urlsafe(24)
    state_payload = {'nonce': nonce, 'integration_id': integration.id}
    state = json.dumps(state_payload)
    request.session['zoom_oauth_nonce'] = nonce
    request.session['zoom_oauth_integration_id'] = integration.id
    return redirect(zoom_authorize_url(state))


@login_required
def chatbot_zoom_connect_callback(request):
    if not request.user.is_authenticated:
        return redirect('login')

    expected_nonce = request.session.get('zoom_oauth_nonce')
    integration_id = request.session.get('zoom_oauth_integration_id')
    returned_state = request.GET.get('state')
    code = request.GET.get('code')
    error = request.GET.get('error')

    if error:
        logger.warning('Zoom OAuth callback returned error=%s state=%s code_present=%s', error, returned_state, bool(code))
        messages.error(request, f'Zoom connection failed: {error}')
        return redirect('chatbot_index')

    state_integration_id = None
    returned_nonce = None
    try:
        state_payload = json.loads(returned_state or '{}')
        returned_nonce = state_payload.get('nonce')
        state_integration_id = state_payload.get('integration_id')
    except Exception:
        state_payload = {}

    integration_id = integration_id or state_integration_id

    if not integration_id and request.user.is_authenticated:
        tenant_id = request.session.get('current_tenant_id')
        if tenant_id:
            zoom_integrations = ChatbotIntegration.objects.filter(
                tenant_id=tenant_id,
                platform=ChatbotIntegration.PLATFORM_ZOOM_CHAT,
            ).order_by('id')
            if zoom_integrations.count() == 1:
                integration_id = zoom_integrations.first().id

    state_invalid = bool(returned_state) and bool(expected_nonce) and bool(returned_nonce) and expected_nonce != returned_nonce
    if not code or not integration_id or state_invalid:
        query_snapshot = {key: request.GET.get(key) for key in request.GET.keys()}
        logger.warning(
            'Zoom OAuth callback invalid state/missing code integration_id=%s session_integration_id=%s state_integration_id=%s expected_nonce=%s returned_nonce=%s code_present=%s raw_state=%s query=%s',
            integration_id,
            request.session.get('zoom_oauth_integration_id'),
            state_integration_id,
            expected_nonce,
            returned_nonce,
            bool(code),
            returned_state,
            query_snapshot,
        )
        messages.error(request, f'Zoom connection failed: invalid OAuth state or missing code. Returned params: {query_snapshot}')
        return redirect('chatbot_index')

    integration = ChatbotIntegration.objects.filter(id=integration_id, platform=ChatbotIntegration.PLATFORM_ZOOM_CHAT).first()
    if integration is None:
        messages.error(request, 'Zoom connection failed: integration not found.')
        return redirect('chatbot_index')

    try:
        tokens = exchange_zoom_code_for_tokens(code)
        access_token = tokens.get('access_token', '')
        logger.info('Zoom OAuth token exchange succeeded integration_id=%s token_keys=%s', integration.id, sorted(tokens.keys()))
        robot_response = requests.get(
            'https://api.zoom.us/v2/im/chat/users/me',
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=30,
        )
        robot_payload = {}
        if robot_response.ok:
            robot_payload = robot_response.json() or {}
        else:
            logger.warning('Zoom bot profile lookup failed integration_id=%s status=%s body=%s', integration.id, robot_response.status_code, robot_response.text[:1000])

        credentials = integration.credentials_json or {}
        credentials.update({
            'access_token': access_token,
            'refresh_token': tokens.get('refresh_token', ''),
            'expires_at': tokens.get('expires_at').isoformat() if tokens.get('expires_at') else '',
        })
        if robot_payload.get('jid'):
            credentials['bot_jid'] = robot_payload.get('jid')
        integration.credentials_json = credentials
        integration.webhook_status = 'connected'
        integration.save(update_fields=['credentials_json', 'webhook_status', 'updated_at'])
        messages.success(request, 'Zoom Chat integration connected. Access token stored.')
    except requests.HTTPError as exc:
        body = ''
        if exc.response is not None:
            body = exc.response.text[:1000]
        logger.exception('Zoom OAuth token exchange failed integration_id=%s body=%s', integration.id, body)
        messages.error(request, f'Zoom connection failed during token exchange: {body or exc}')
    except Exception as exc:
        logger.exception('Zoom OAuth callback failed integration_id=%s', integration.id)
        messages.error(request, f'Zoom connection failed: {exc}')
    return redirect('chatbot_index')


@login_required
@login_required
def chatbot_event_detail(request, event_id):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')

    event = get_object_or_404(
        ChatbotEventLog.objects.select_related('integration', 'endpoint', 'bot_definition'),
        id=event_id,
        tenant=tenant,
    )
    base.update({
        'section': 'chatbots',
        'chatbot_subsection': 'event_detail',
        'chatbot_event': event,
    })
    return render(request, 'dashboard/chatbot_event_detail.html', base)


@login_required
def chatbot_definition_detail(request, definition_id):
    base = _dashboard_base(request)
    handled = _handle_workspace_actions(request, base)
    if handled:
        return handled

    tenant = base.get('current_tenant')
    if tenant is None:
        messages.error(request, 'No tenant selected.')
        return redirect('dashboard')

    definition = get_object_or_404(
        ChatbotDefinition.objects.select_related('integration', 'default_workspace'),
        id=definition_id,
        tenant=tenant,
    )
    base.update({
        'section': 'chatbots',
        'chatbot_subsection': 'definition_detail',
        'chatbot_definition': definition,
        'chatbot_bindings': definition.endpoint_bindings.select_related('endpoint', 'workspace_override').order_by('endpoint__display_name'),
        'chatbot_builds': definition.builds.order_by('-created_at')[:25],
        'chatbot_deployments': definition.deployments.select_related('build').order_by('-created_at')[:25],
    })
    return render(request, 'dashboard/chatbot_definition_detail.html', base)
