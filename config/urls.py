from django.contrib import admin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import path
from documents.api import DocumentCreateView, DocumentDeleteView, DocumentPurgeView, DocumentRestoreView, URLIngestView
from control.views import AppLoginView, dashboard, dashboard_api_keys, dashboard_chat, dashboard_connectors, dashboard_documents, dashboard_urls, document_download, logout_view, microsoft_connect_callback, microsoft_connect_start, signup, staff_dashboard
from retrieval.api import ChatView, SearchView


def home(request):
    return render(request, 'home.html')


def health(_request):
    return JsonResponse({'ok': True, 'service': 'docstore-rag'})


def offline(request):
    return render(request, 'offline.html')


def service_worker(_request):
    return HttpResponse(render_to_string('sw.js'), content_type='application/javascript')


def manifest(_request):
    return HttpResponse(render_to_string('manifest.webmanifest'), content_type='application/manifest+json')


urlpatterns = [
    path('', home),
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
    path('documents/<int:document_id>/download/', document_download, name='document_download'),
    path('dashboard/connectors/', dashboard_connectors, name='dashboard_connectors'),
    path('dashboard/api-keys/', dashboard_api_keys, name='dashboard_api_keys'),
    path('dashboard/staff/', staff_dashboard, name='staff_dashboard'),
    path('connect/microsoft/', microsoft_connect_start, name='microsoft_connect_start'),
    path('connect/microsoft/callback/', microsoft_connect_callback, name='microsoft_connect_callback'),
    path('api/v1/documents/', DocumentCreateView.as_view()),
    path('api/v1/documents/delete/', DocumentDeleteView.as_view()),
    path('api/v1/documents/restore/', DocumentRestoreView.as_view()),
    path('api/v1/documents/purge/', DocumentPurgeView.as_view()),
    path('api/v1/urls/ingest/', URLIngestView.as_view()),
    path('api/v1/search/', SearchView.as_view()),
    path('api/v1/chat/', ChatView.as_view()),
    path('admin/', admin.site.urls),
    path('healthz/', health),
]
