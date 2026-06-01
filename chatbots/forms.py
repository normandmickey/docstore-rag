import json

from django import forms

from control.models import Workspace

from .models import ChatbotDefinition, ChatbotEndpoint, ChatbotEndpointBinding, ChatbotIntegration


PLATFORM_DEFINITION_PRESETS = {
    ChatbotIntegration.PLATFORM_TELEGRAM: {
        'template_name': 'telegram-assistant',
        'template_version': 'v1',
        'persona_prompt': 'You are a concise document assistant for Telegram. Be helpful, direct, and mobile-friendly.',
        'system_prompt': 'Answer using the current workspace documents. Keep replies short and easy to read on mobile. Prefer a direct answer first, then a short supporting detail if needed.',
        'allowed_tools_json': {'web_search': False},
        'response_policy_json': {'style': 'concise', 'markdown': 'light', 'channel_behavior': 'dm-first'},
        'handoff_policy_json': {'allow_human_handoff': True},
        'logging_policy_json': {'store_raw_events': True},
        'metadata_json': {'prefill_source': 'telegram'},
    },
    ChatbotIntegration.PLATFORM_DISCORD: {
        'template_name': 'discord-assistant',
        'template_version': 'v1',
        'persona_prompt': 'You are a concise document assistant for Discord. Be helpful, natural, and not overly formal.',
        'system_prompt': 'Answer from the current workspace documents. In DMs, reply directly. In servers, assume mention-first behavior and keep responses channel-friendly.',
        'allowed_tools_json': {'web_search': False},
        'response_policy_json': {'style': 'concise', 'markdown': 'light', 'channel_behavior': 'dm-reply-mention-server'},
        'handoff_policy_json': {'allow_human_handoff': True},
        'logging_policy_json': {'store_raw_events': True},
        'metadata_json': {'prefill_source': 'discord'},
    },
    ChatbotIntegration.PLATFORM_ZOOM_CHAT: {
        'template_name': 'zoom-chat-assistant',
        'template_version': 'v1',
        'persona_prompt': 'You are a concise support and document assistant for Zoom Team Chat. Sound helpful and natural.',
        'system_prompt': 'Answer using the current workspace documents. Keep responses short, clear, and professional. Avoid heavy markdown and lead with the direct answer.',
        'allowed_tools_json': {'web_search': False},
        'response_policy_json': {'style': 'concise', 'markdown': 'minimal', 'channel_behavior': 'team-chat'},
        'handoff_policy_json': {'allow_human_handoff': True},
        'logging_policy_json': {'store_raw_events': True},
        'metadata_json': {'prefill_source': 'zoom_chat'},
    },
}


class ChatbotIntegrationForm(forms.ModelForm):
    class Meta:
        model = ChatbotIntegration
        fields = [
            'platform',
            'name',
            'status',
            'active',
            'external_app_id',
            'external_bot_id',
            'webhook_url',
            'webhook_status',
            'credentials_json',
            'metadata_json',
        ]
        widgets = {
            'webhook_url': forms.URLInput(attrs={'style': 'width: 100%;'}),
            'credentials_json': forms.Textarea(attrs={'rows': 6}),
            'metadata_json': forms.Textarea(attrs={'rows': 4}),
        }
        help_texts = {
            'external_app_id': 'For Zoom Chat, store the Zoom app/client id here so webhook events can resolve the correct integration.',
            'external_bot_id': 'Optional platform bot identity. Used today for Discord; reserved for future Zoom send-side identity if needed.',
            'credentials_json': 'Telegram stores bot_token here. Zoom Chat can store app/install metadata here later, but outbound send is not wired yet.',
            'metadata_json': 'Optional setup notes or platform-specific metadata. For Zoom Chat, this is a good place to store team/admin notes during bring-up.',
        }


class ChatbotDefinitionForm(forms.ModelForm):
    prefill_from_integration = forms.BooleanField(
        required=False,
        initial=True,
        label='Prefill from integration',
        help_text='For new definitions, use the selected integration to prefill blank prompts and default settings.',
    )
    response_temperature = forms.FloatField(
        required=False,
        min_value=0,
        max_value=2,
        label='Response temperature',
        help_text='Controls how steady or creative the bot’s grounded reply should be. Leave blank to use the default.',
    )
    rewrite_temperature = forms.FloatField(
        required=False,
        min_value=0,
        max_value=2,
        label='Rewrite temperature',
        help_text='Controls how much the final wording can vary when the bot polishes a reply before sending it. Leave blank to use the default.',
    )

    class Meta:
        model = ChatbotDefinition
        fields = [
            'integration',
            'name',
            'default_workspace',
            'persona_prompt',
            'system_prompt',
            'runtime_mode',
            'template_name',
            'template_version',
            'response_temperature',
            'rewrite_temperature',
            'allowed_tools_json',
            'response_policy_json',
            'handoff_policy_json',
            'logging_policy_json',
            'active',
            'metadata_json',
        ]
        widgets = {
            'persona_prompt': forms.Textarea(attrs={'rows': 5}),
            'system_prompt': forms.Textarea(attrs={'rows': 8}),
            'allowed_tools_json': forms.Textarea(attrs={'rows': 4}),
            'response_policy_json': forms.Textarea(attrs={'rows': 4}),
            'handoff_policy_json': forms.Textarea(attrs={'rows': 4}),
            'logging_policy_json': forms.Textarea(attrs={'rows': 4}),
            'metadata_json': forms.Textarea(attrs={'rows': 4}),
        }
        labels = {
            'allowed_tools_json': 'Allowed tools JSON',
            'response_policy_json': 'Response policy JSON',
            'handoff_policy_json': 'Handoff policy JSON',
            'logging_policy_json': 'Logging policy JSON',
            'metadata_json': 'Metadata JSON',
        }
        help_texts = {
            'allowed_tools_json': 'Optional tool access and capability flags for this bot definition.',
            'response_policy_json': 'Optional reply-style and channel-behavior settings.',
            'handoff_policy_json': 'Optional handoff and escalation settings.',
            'logging_policy_json': 'Optional controls for what chatbot activity gets stored.',
            'metadata_json': 'Optional extra settings for this definition that do not belong in prompts or policy fields.',
        }

    def __init__(self, *args, tenant=None, **kwargs):
        self.prefill_enabled = kwargs.pop('prefill_enabled', True)
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields['integration'].queryset = ChatbotIntegration.objects.filter(tenant=tenant).order_by('platform', 'name')
            self.fields['default_workspace'].queryset = Workspace.objects.filter(tenant=tenant).order_by('name')
        else:
            self.fields['integration'].queryset = ChatbotIntegration.objects.none()
            self.fields['default_workspace'].queryset = Workspace.objects.none()
        json_field_names = [
            'allowed_tools_json',
            'response_policy_json',
            'handoff_policy_json',
            'logging_policy_json',
            'metadata_json',
        ]
        for field_name in json_field_names:
            if field_name in self.fields:
                self.fields[field_name].initial = json.dumps(getattr(self.instance, field_name, {}) or {}, indent=2, sort_keys=True)
        metadata = getattr(self.instance, 'metadata_json', {}) or {}
        self.fields['response_temperature'].initial = metadata.get('response_temperature')
        self.fields['rewrite_temperature'].initial = metadata.get('rewrite_temperature')
        if self.instance and self.instance.pk:
            self.fields['integration'].initial = self.instance.integration_id
            self.fields['default_workspace'].initial = self.instance.default_workspace_id
            self.fields['persona_prompt'].initial = self.instance.persona_prompt
            self.fields['system_prompt'].initial = self.instance.system_prompt
            self.fields['runtime_mode'].initial = self.instance.runtime_mode
            self.fields['template_name'].initial = self.instance.template_name
            self.fields['template_version'].initial = self.instance.template_version
            self.fields['name'].initial = self.instance.name
            self.fields['active'].initial = self.instance.active
            self.fields['prefill_from_integration'].initial = False

    def clean_integration(self):
        integration = self.cleaned_data.get('integration')
        if integration and self.tenant and integration.tenant_id != self.tenant.id:
            raise forms.ValidationError('Selected integration does not belong to the current tenant.')
        return integration

    def clean_default_workspace(self):
        workspace = self.cleaned_data.get('default_workspace')
        if workspace and self.tenant and workspace.tenant_id != self.tenant.id:
            raise forms.ValidationError('Selected workspace does not belong to the current tenant.')
        return workspace

    def save(self, commit=True):
        instance = super().save(commit=False)
        should_prefill = self.cleaned_data.get('prefill_from_integration') and self.prefill_enabled
        integration = self.cleaned_data.get('integration') or getattr(instance, 'integration', None)
        preset = PLATFORM_DEFINITION_PRESETS.get(getattr(integration, 'platform', None)) if integration else None
        if should_prefill and preset:
            for field_name, preset_value in preset.items():
                current_value = getattr(instance, field_name)
                if current_value not in (None, '', {}):
                    continue
                if isinstance(preset_value, dict):
                    setattr(instance, field_name, json.loads(json.dumps(preset_value)))
                else:
                    setattr(instance, field_name, preset_value)
        metadata = dict(getattr(instance, 'metadata_json', {}) or {})
        response_temperature = self.cleaned_data.get('response_temperature')
        rewrite_temperature = self.cleaned_data.get('rewrite_temperature')
        if response_temperature is None:
            metadata.pop('response_temperature', None)
        else:
            metadata['response_temperature'] = response_temperature
        if rewrite_temperature is None:
            metadata.pop('rewrite_temperature', None)
        else:
            metadata['rewrite_temperature'] = rewrite_temperature
        instance.metadata_json = metadata
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ChatbotEndpointForm(forms.ModelForm):
    class Meta:
        model = ChatbotEndpoint
        fields = [
            'integration',
            'endpoint_type',
            'external_id',
            'external_parent_id',
            'display_name',
            'default_workspace',
            'mode',
            'active',
            'metadata_json',
        ]
        widgets = {
            'metadata_json': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields['integration'].queryset = ChatbotIntegration.objects.filter(tenant=tenant).order_by('platform', 'name')
            self.fields['default_workspace'].queryset = Workspace.objects.filter(tenant=tenant).order_by('name')
        else:
            self.fields['integration'].queryset = ChatbotIntegration.objects.none()
            self.fields['default_workspace'].queryset = Workspace.objects.none()

    def clean_integration(self):
        integration = self.cleaned_data.get('integration')
        if integration and self.tenant and integration.tenant_id != self.tenant.id:
            raise forms.ValidationError('Selected integration does not belong to the current tenant.')
        return integration

    def clean_default_workspace(self):
        workspace = self.cleaned_data.get('default_workspace')
        if workspace and self.tenant and workspace.tenant_id != self.tenant.id:
            raise forms.ValidationError('Selected workspace does not belong to the current tenant.')
        return workspace


class ChatbotEndpointBindingForm(forms.ModelForm):
    class Meta:
        model = ChatbotEndpointBinding
        fields = ['bot_definition', 'endpoint', 'workspace_override', 'active', 'metadata_json']
        widgets = {
            'metadata_json': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields['bot_definition'].queryset = ChatbotDefinition.objects.filter(tenant=tenant).order_by('name')
            self.fields['endpoint'].queryset = ChatbotEndpoint.objects.filter(tenant=tenant).order_by('display_name')
            self.fields['workspace_override'].queryset = Workspace.objects.filter(tenant=tenant).order_by('name')
        else:
            self.fields['bot_definition'].queryset = ChatbotDefinition.objects.none()
            self.fields['endpoint'].queryset = ChatbotEndpoint.objects.none()
            self.fields['workspace_override'].queryset = Workspace.objects.none()

    def clean_bot_definition(self):
        bot_definition = self.cleaned_data.get('bot_definition')
        if bot_definition and self.tenant and bot_definition.tenant_id != self.tenant.id:
            raise forms.ValidationError('Selected bot definition does not belong to the current tenant.')
        return bot_definition

    def clean_endpoint(self):
        endpoint = self.cleaned_data.get('endpoint')
        if endpoint and self.tenant and endpoint.tenant_id != self.tenant.id:
            raise forms.ValidationError('Selected endpoint does not belong to the current tenant.')
        return endpoint

    def clean_workspace_override(self):
        workspace = self.cleaned_data.get('workspace_override')
        if workspace and self.tenant and workspace.tenant_id != self.tenant.id:
            raise forms.ValidationError('Selected workspace does not belong to the current tenant.')
        return workspace
