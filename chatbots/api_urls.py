from django.urls import path

from .api import ChatbotEventIngestView, ChatbotMessageIngestView, ChatbotResolveView

urlpatterns = [
    path('resolve/', ChatbotResolveView.as_view()),
    path('events/ingest/', ChatbotEventIngestView.as_view()),
    path('messages/ingest/', ChatbotMessageIngestView.as_view()),
]
