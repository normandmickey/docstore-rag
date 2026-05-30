from django.urls import path

from .views import support_channel_edit, support_channel_new, support_channels, support_conversation_detail, support_index, twilio_sms_inbound, twilio_sms_status

urlpatterns = [
    path('', support_index, name='support_index'),
    path('channels/', support_channels, name='support_channels'),
    path('channels/new/', support_channel_new, name='support_channel_new'),
    path('channels/<int:channel_id>/edit/', support_channel_edit, name='support_channel_edit'),
    path('conversations/<int:conversation_id>/', support_conversation_detail, name='support_conversation_detail'),
    path('sms/inbound/', twilio_sms_inbound, name='twilio_sms_inbound'),
    path('sms/status/', twilio_sms_status, name='twilio_sms_status'),
]
