from django.contrib import admin

from .models import SupportChannel, SupportContact, SupportConversation, SupportMessage


@admin.register(SupportChannel)
class SupportChannelAdmin(admin.ModelAdmin):
    list_display = ('name', 'tenant', 'channel_type', 'twilio_phone_number', 'default_workspace', 'active', 'ai_enabled', 'auto_reply_enabled')
    search_fields = ('name', 'tenant__name', 'twilio_phone_number', 'twilio_phone_number_sid')
    list_filter = ('channel_type', 'active', 'ai_enabled', 'auto_reply_enabled', 'tenant')


@admin.register(SupportContact)
class SupportContactAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'name', 'tenant', 'external_ref', 'updated_at')
    search_fields = ('phone_number', 'name', 'external_ref', 'tenant__name')
    list_filter = ('tenant',)


@admin.register(SupportConversation)
class SupportConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'tenant', 'channel', 'contact', 'workspace_context', 'status', 'assigned_user', 'last_message_at', 'updated_at')
    search_fields = ('contact__phone_number', 'contact__name', 'subject', 'tenant__name', 'channel__name')
    list_filter = ('tenant', 'status', 'channel', 'workspace_context')


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'direction', 'kind', 'provider_message_sid', 'delivery_status', 'sent_by_user', 'created_at')
    search_fields = ('body', 'provider_message_sid', 'conversation__contact__phone_number', 'conversation__tenant__name')
    list_filter = ('direction', 'kind', 'delivery_status')
