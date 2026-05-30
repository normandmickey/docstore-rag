from django.urls import path

from .views import ingest_voice_call

urlpatterns = [
    path('calls/ingest/', ingest_voice_call, name='ingest_voice_call'),
]
