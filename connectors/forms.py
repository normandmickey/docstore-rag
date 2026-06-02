from django import forms

from .models import TenantShippingIntegration


class TenantShippingIntegrationForm(forms.ModelForm):
    api_key = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text='Stored for this tenant and used for shipping-manager API calls.',
    )

    class Meta:
        model = TenantShippingIntegration
        fields = ['label', 'base_url', 'api_key', 'status']
        widgets = {
            'label': forms.TextInput(attrs={'placeholder': 'Shipping Manager'}),
            'base_url': forms.URLInput(attrs={'placeholder': 'https://ship.example.com'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        api_key = (self.cleaned_data.get('api_key') or '').strip()
        if api_key:
            instance.api_key = api_key
        if commit:
            instance.save()
        return instance
