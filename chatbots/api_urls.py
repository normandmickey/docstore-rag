from django.urls import path

from .api import ChatbotConversationContextView, ChatbotEventIngestView, ChatbotMessageIngestView, ChatbotResolveView

urlpatterns = [
    path('resolve/', ChatbotResolveView.as_view()),
    path('context/', ChatbotConversationContextView.as_view()),
    path('events/ingest/', ChatbotEventIngestView.as_view()),
    path('messages/ingest/', ChatbotMessageIngestView.as_view()),
]
