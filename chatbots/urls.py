from django.urls import path

from .views import chatbot_index

urlpatterns = [
    path('', chatbot_index, name='chatbot_index'),
]
