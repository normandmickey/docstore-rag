from django.contrib import admin
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import path


def home(request):
    return render(request, 'home.html')


def health(_request):
    return JsonResponse({'ok': True, 'service': 'docstore-rag'})


urlpatterns = [
    path('', home),
    path('admin/', admin.site.urls),
    path('healthz/', health),
]
