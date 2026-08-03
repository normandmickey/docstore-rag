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
    """Handle Google sign-in users: create account + bootstrap workspace."""

    def pre_social_login(self, request, sociallogin):
        """If the user already exists, let allauth log them in.
        If new, we'll handle in save_user / post_social_login."""
        pass

    def save_user(self, request, sociallogin):
        """Create or get the user from Google OAuth."""
        from django.contrib.auth import get_user_model
        from django.utils.text import slugify
        from control.models import Tenant, TenantMembership, Workspace

        User = get_user_model()
        email = sociallogin.account.extra_data.get('email', '')
        google_sub = sociallogin.account.uid

        # Try to find existing user by email
        user = User.objects.filter(email=email).first()
        if user:
            # Link the social account to existing user
            sociallogin.account.user = user
            sociallogin.account.save()
            return user

        # Create new user
        name = sociallogin.account.extra_data.get('name', '')
        given = sociallogin.account.extra_data.get('given_name', '')
        family = sociallogin.account.extra_data.get('family_name', '')

        # Generate username from email or name
        base = email.split('@')[0] if email else (slugify(name) or f'user-{google_sub[:8]}')
        username = base
        i = 2
        while User.objects.filter(username=username).exists():
            username = f'{base}-{i}'
            i += 1

        user = User.objects.create_user(
            username=username,
            email=email,
            password=None,  # No password for Google-only users
        )
        user.first_name = given
        user.last_name = family
        user.save()

        # Bootstrap their workspace (same as signup flow)
        tenant_slug = base
        i = 2
        while Tenant.objects.filter(slug=tenant_slug).exists():
            tenant_slug = f'{base}-{i}'
            i += 1

        tenant = Tenant.objects.create(name=f"{username}'s Workspace", slug=tenant_slug)
        TenantMembership.objects.create(
            tenant=tenant, user=user, role=TenantMembership.ROLE_OWNER,
        )
        Workspace.objects.create(tenant=tenant, name='Default Workspace', slug='default')

        sociallogin.account.user = user
        sociallogin.account.save()

        return user

    def post_social_login(self, request, sociallogin):
        """Set session after Google login."""
        from control.views import _bootstrap_user_workspace

        user = sociallogin.account.user
        if not request.session.get('current_tenant_id'):
            membership = user.tenantmembership_set.first()
            if membership:
                request.session['current_tenant_id'] = membership.tenant_id
                if not request.session.get('current_workspace_id'):
                    workspace = membership.tenant.workspaces.order_by('created_at').first()
                    if workspace:
                        request.session['current_workspace_id'] = workspace.id
