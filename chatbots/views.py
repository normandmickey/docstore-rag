from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from control.views import _dashboard_base, _handle_workspace_actions

from .models import ChatbotBuild, ChatbotDefinition, ChatbotDeployment, ChatbotEventLog, ChatbotIntegration


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
        'chatbot_deployments': ChatbotDeployment.objects.filter(bot_definition__tenant=tenant).select_related('bot_definition', 'build').order_by('-created_at')[:25],
        'chatbot_recent_builds': ChatbotBuild.objects.filter(bot_definition__tenant=tenant).select_related('bot_definition').order_by('-created_at')[:25],
        'chatbot_recent_events': ChatbotEventLog.objects.filter(tenant=tenant).select_related('integration', 'endpoint', 'bot_definition').order_by('-created_at')[:25],
    })
    return render(request, 'dashboard/chatbots.html', base)
