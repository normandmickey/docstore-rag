from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.template.loader import render_to_string

from control.agentmail import AgentMailClient


class DocstoreAccountAdapter(DefaultAccountAdapter):
    def send_mail(self, template_prefix: str, email: str, context: dict) -> None:
        to = [email] if isinstance(email, str) else list(email)
        subject = render_to_string(f'{template_prefix}_subject.txt', context)
        subject = ' '.join(subject.splitlines()).strip()
        subject = self.format_email_subject(subject)

        bodies = {}
        html_ext = 'html'
        for ext in [html_ext, 'txt']:
            try:
                template_name = f'{template_prefix}_message.{ext}'
                bodies[ext] = render_to_string(template_name, context).strip()
            except Exception:
                continue

        text = bodies.get('txt', '')
        html = bodies.get(html_ext, '')
        AgentMailClient().send_message(
            to=to,
            subject=subject,
            text=text,
            html=html,
        )


class DocstoreSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Handle Google sign-in: auto-link existing users, bootstrap workspace for new ones."""

    def save_user(self, request, sociallogin, form=None):
        """Create the user via allauth's default, then bootstrap workspace."""
        from django.utils.text import slugify
        from control.models import Tenant, TenantMembership, Workspace

        user = super().save_user(request, sociallogin, form=form)

        # Only bootstrap for brand-new auto-signup users (no form)
        if form is None and not user.tenantmembership_set.exists():
            base = slugify(user.username) or f'user-{user.id}'
            tenant_slug = base
            i = 2
            while Tenant.objects.filter(slug=tenant_slug).exists():
                tenant_slug = f'{base}-{i}'
                i += 1

            tenant = Tenant.objects.create(
                name=f"{user.username}'s Workspace",
                slug=tenant_slug,
            )
            TenantMembership.objects.create(
                tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER,
            )
            Workspace.objects.create(
                tenant=tenant, name='Default Workspace', slug='default',
            )

        return user

    def post_social_login(self, request, sociallogin):
        """Set session after Google login."""
        user = sociallogin.account.user
        if not request.session.get('current_tenant_id'):
            membership = user.tenantmembership_set.first()
            if membership:
                request.session['current_tenant_id'] = membership.tenant_id
                if not request.session.get('current_workspace_id'):
                    workspace = membership.tenant.workspaces.order_by('created_at').first()
                    if workspace:
                        request.session['current_workspace_id'] = workspace.id

    def is_auto_signup_allowed(self, request, sociallogin):
        """Allow auto-signup for Google accounts with email."""
        email = None
        if sociallogin.email_addresses:
            email = sociallogin.email_addresses[0].email
        elif sociallogin.account.extra_data.get('email'):
            email = sociallogin.account.extra_data['email']
        return bool(email)