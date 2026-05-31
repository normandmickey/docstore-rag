from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from control.views import _dashboard_base, _handle_workspace_actions

from .forms import ChatbotDefinitionForm, ChatbotEndpointBindingForm, ChatbotEndpointForm, ChatbotIntegrationForm
from .models import ChatbotBuild, ChatbotDefinition, ChatbotDeployment, ChatbotEndpoint, ChatbotEndpointBinding, ChatbotEventLog, ChatbotIntegration


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
