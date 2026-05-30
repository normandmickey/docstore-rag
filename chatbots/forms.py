from django import forms

from control.models import Workspace

from .models import ChatbotDefinition, ChatbotEndpoint, ChatbotEndpointBinding, ChatbotIntegration


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
            'runner_key',
            'credentials_json',
            'metadata_json',
        ]
        widgets = {
            'runner_key': forms.TextInput(attrs={'readonly': 'readonly'}),
            'credentials_json': forms.Textarea(attrs={'rows': 6}),
            'metadata_json': forms.Textarea(attrs={'rows': 4}),
        }


class ChatbotDefinitionForm(forms.ModelForm):
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
