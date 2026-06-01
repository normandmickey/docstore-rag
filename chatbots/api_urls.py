from django.urls import path

from .api import ChatbotConversationContextView, ChatbotEventIngestView, ChatbotMessageIngestView, ChatbotReplyRewriteView, ChatbotResolveView

urlpatterns = [
    path('resolve/', ChatbotResolveView.as_view()),
    path('context/', ChatbotConversationContextView.as_view()),
    path('rewrite-reply/', ChatbotReplyRewriteView.as_view()),
    path('events/ingest/', ChatbotEventIngestView.as_view()),
    path('messages/ingest/', ChatbotMessageIngestView.as_view()),
]
