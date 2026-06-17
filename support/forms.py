from django import forms

from control.models import Workspace

from .models import SupportChannel, SupportConversation


class SupportChannelForm(forms.ModelForm):
    class Meta:
        model = SupportChannel
        fields = ['name', 'channel_type', 'twilio_phone_number', 'twilio_phone_number_sid', 'default_workspace', 'active', 'ai_enabled', 'auto_reply_enabled']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields['default_workspace'].queryset = Workspace.objects.filter(tenant=tenant).order_by('name')
        else:
            self.fields['default_workspace'].queryset = Workspace.objects.none()

    def clean_default_workspace(self):
        workspace = self.cleaned_data.get('default_workspace')
        if workspace and self.tenant and workspace.tenant_id != self.tenant.id:
            raise forms.ValidationError('Selected workspace does not belong to the current tenant.')
        return workspace


class SupportReplyForm(forms.Form):
    body = forms.CharField(widget=forms.Textarea(attrs={'rows': 4}), max_length=5000, required=False)


class SupportConversationUpdateForm(forms.ModelForm):
    class Meta:
        model = SupportConversation
        fields = ['status', 'assigned_user', 'workspace_context']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        if tenant is not None:
            self.fields['workspace_context'].queryset = Workspace.objects.filter(tenant=tenant).order_by('name')
            self.fields['assigned_user'].queryset = self.fields['assigned_user'].queryset.filter(tenant_memberships__tenant=tenant).distinct().order_by('username')
        else:
            self.fields['workspace_context'].queryset = Workspace.objects.none()
            self.fields['assigned_user'].queryset = self.fields['assigned_user'].queryset.none()

    def clean_workspace_context(self):
        workspace = self.cleaned_data.get('workspace_context')
        if workspace and self.tenant and workspace.tenant_id != self.tenant.id:
            raise forms.ValidationError('Selected workspace does not belong to the current tenant.')
        return workspace
