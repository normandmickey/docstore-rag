from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def health(_request):
    return JsonResponse({'ok': True, 'service': 'docstore-rag'})


urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz/', health),
]
