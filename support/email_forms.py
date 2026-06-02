from django import forms

from control.models import Workspace

from .models import TenantEmailIntegration


class TenantEmailIntegrationForm(forms.ModelForm):
    api_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text='Stored for this tenant and used for AgentMail send/receive flows.',
    )

    class Meta:
        model = TenantEmailIntegration
        fields = ['label', 'from_name', 'from_email', 'inbox_id', 'api_key', 'default_workspace', 'status', 'auto_reply_enabled']
        widgets = {
            'label': forms.TextInput(attrs={'placeholder': 'Support Email'}),
            'from_name': forms.TextInput(attrs={'placeholder': 'Support Team'}),
            'from_email': forms.EmailInput(attrs={'placeholder': 'support@example.com'}),
            'inbox_id': forms.TextInput(attrs={'placeholder': 'agentmail inbox id'}),
        }

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

    def save(self, commit=True):
        instance = super().save(commit=False)
        api_key = (self.cleaned_data.get('api_key') or '').strip()
        if api_key:
            instance.api_key = api_key
        if commit:
            instance.save()
        return instance
