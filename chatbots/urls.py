from django.urls import path

from .views import chatbot_binding_new, chatbot_definition_detail, chatbot_definition_new, chatbot_endpoint_new, chatbot_index, chatbot_integration_edit, chatbot_integration_new, chatbot_zoom_connect_callback, chatbot_zoom_connect_start

urlpatterns = [
    path('', chatbot_index, name='chatbot_index'),
    path('integrations/new/', chatbot_integration_new, name='chatbot_integration_new'),
    path('integrations/<int:integration_id>/edit/', chatbot_integration_edit, name='chatbot_integration_edit'),
    path('integrations/<int:integration_id>/zoom/connect/', chatbot_zoom_connect_start, name='chatbot_zoom_connect_start'),
    path('integrations/zoom/callback/', chatbot_zoom_connect_callback, name='chatbot_zoom_connect_callback'),
    path('definitions/new/', chatbot_definition_new, name='chatbot_definition_new'),
    path('definitions/<int:definition_id>/', chatbot_definition_detail, name='chatbot_definition_detail'),
    path('endpoints/new/', chatbot_endpoint_new, name='chatbot_endpoint_new'),
    path('bindings/new/', chatbot_binding_new, name='chatbot_binding_new'),
]
