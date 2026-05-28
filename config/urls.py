from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import path
from documents.api import DocumentCreateView, DocumentDeleteView, URLIngestView
from control.views import AppLoginView, dashboard, logout_view, microsoft_connect_callback, microsoft_connect_start, signup
from retrieval.api import SearchView


def home(request):
    return render(request, 'home.html')


def health(_request):
    return JsonResponse({'ok': True, 'service': 'docstore-rag'})


urlpatterns = [
    path('', home),
    path('login/', AppLoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('signup/', signup, name='signup'),
    path('dashboard/', dashboard, name='dashboard'),
    path('connect/microsoft/', microsoft_connect_start, name='microsoft_connect_start'),
    path('connect/microsoft/callback/', microsoft_connect_callback, name='microsoft_connect_callback'),
    path('api/v1/documents/', DocumentCreateView.as_view()),
    path('api/v1/documents/delete/', DocumentDeleteView.as_view()),
    path('api/v1/urls/ingest/', URLIngestView.as_view()),
    path('api/v1/search/', SearchView.as_view()),
    path('admin/', admin.site.urls),
    path('healthz/', health),
]
