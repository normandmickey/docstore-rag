from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import path
from documents.api import DocumentCreateView
from retrieval.api import SearchView


def home(request):
    return render(request, 'home.html')


def health(_request):
    return JsonResponse({'ok': True, 'service': 'docstore-rag'})


urlpatterns = [
    path('', home),
    path('api/v1/documents/', DocumentCreateView.as_view()),
    path('api/v1/search/', SearchView.as_view()),
    path('admin/', admin.site.urls),
    path('healthz/', health),
]
