from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from documents.api import DocumentCreateView, DocumentDeleteView, DocumentPurgeView, DocumentRestoreView, URLIngestView
from control.views import AppLoginView, api_quickstart, dashboard, dashboard_api_keys, dashboard_chat, dashboard_connectors, dashboard_documents, dashboard_proxi_web, dashboard_tenant_settings, dashboard_urls, document_chunks, document_detail, document_download, document_facts, document_search, google_connect_callback, google_connect_start, logout_view, microsoft_connect_callback, microsoft_connect_start, signup, staff_dashboard
from retrieval.api import ChatView, SearchView
from support.api import SupportChannelLookupView


def home(request):
    return render(request, 'home.html')


def health(_request):
    return JsonResponse({'ok': True, 'service': 'docstore-rag'})


def privacy(request):
    return render(request, 'privacy.html')


def terms(request):
    return render(request, 'terms.html')


def offline(request):
    return render(request, 'offline.html')


def service_worker(_request):
    return HttpResponse(render_to_string('sw.js'), content_type='application/javascript')


def manifest(_request):
    return HttpResponse(render_to_string('manifest.webmanifest'), content_type='application/manifest+json')


urlpatterns = [
    path('', home),
    path('privacy/', privacy, name='privacy'),
    path('terms/', terms, name='terms'),
    path('offline/', offline, name='offline'),
    path('sw.js', service_worker, name='service_worker'),
    path('manifest.webmanifest', manifest, name='manifest'),
    path('login/', AppLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('signup/', signup, name='signup'),
    path('dashboard/', dashboard, name='dashboard'),
    path('dashboard/documents/', dashboard_documents, name='dashboard_documents'),
    path('dashboard/urls/', dashboard_urls, name='dashboard_urls'),
    path('dashboard/chat/', dashboard_chat, name='dashboard_chat'),
    path('dashboard/proxi-web/', dashboard_proxi_web, name='dashboard_proxi_web'),
    path('dashboard/chatbots/', include('chatbots.urls')),
    path('documents/<int:document_id>/', document_detail, name='document_detail'),
    path('documents/<int:document_id>/facts/', document_facts, name='document_facts'),
    path('documents/<int:document_id>/chunks/', document_chunks, name='document_chunks'),
    path('documents/<int:document_id>/search/', document_search, name='document_search'),
    path('documents/<int:document_id>/download/', document_download, name='document_download'),
    path('dashboard/connectors/', dashboard_connectors, name='dashboard_connectors'),
    path('dashboard/tenant/', dashboard_tenant_settings, name='dashboard_tenant_settings'),
    path('dashboard/api-keys/', dashboard_api_keys, name='dashboard_api_keys'),
    path('dashboard/support/', include('support.urls')),
    path('dashboard/reports/', include('reports.urls')),
    path('twilio/webhooks/', include('support.urls')),
    path('dashboard/staff/', staff_dashboard, name='staff_dashboard'),
    path('connect/microsoft/', microsoft_connect_start, name='microsoft_connect_start'),
    path('connect/microsoft/callback/', microsoft_connect_callback, name='microsoft_connect_callback'),
    path('connect/google/', google_connect_start, name='google_connect_start'),
    path('connect/google/callback/', google_connect_callback, name='google_connect_callback'),
    path('api/quickstart/', api_quickstart, name='api_quickstart'),
    path('api/schema/', SpectacularAPIView.as_view(), name='api_schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='api_schema'), name='api_docs'),
    path('api/v1/documents/', DocumentCreateView.as_view()),
    path('api/v1/documents/delete/', DocumentDeleteView.as_view()),
    path('api/v1/documents/restore/', DocumentRestoreView.as_view()),
    path('api/v1/documents/purge/', DocumentPurgeView.as_view()),
    path('api/v1/urls/ingest/', URLIngestView.as_view()),
    path('api/v1/search/', SearchView.as_view()),
    path('api/v1/chat/', ChatView.as_view()),
    path('api/v1/support/channel-lookup/', SupportChannelLookupView.as_view()),
    path('api/v1/chatbots/', include('chatbots.api_urls')),
    path('api/v1/integrations/voice/', include('integrations.voice.urls')),
    path('admin/', admin.site.urls),
    path('healthz/', health),
]
