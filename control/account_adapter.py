from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.socialaccount.internal import flows
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
    """Handle Google sign-in: link to existing users, auto-signup new ones."""

    def pre_social_login(self, request, sociallogin):
        """If the Google email matches an existing user, log them in directly."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        email = None
        if sociallogin.email_addresses:
            email = sociallogin.email_addresses[0].email
        elif sociallogin.account.extra_data.get('email'):
            email = sociallogin.account.extra_data['email']

        if not email:
            return

        existing_user = User.objects.filter(email=email).first()
        if not existing_user:
            return

        # Link the social account to the existing user if not already linked
        from allauth.socialaccount.models import SocialAccount
        account, created = SocialAccount.objects.get_or_create(
            provider=sociallogin.account.provider,
            uid=sociallogin.account.uid,
            defaults={'user': existing_user},
        )
        if created:
            account.user = existing_user
            account.save()

        # Connect the sociallogin to the existing user
        sociallogin.account.user = existing_user
        sociallogin.user = existing_user

        # Complete login directly — bypasses the signup form
        from allauth.socialaccount.helpers import complete_social_login
        flows.signup.clear_pending_signup(request)
        return complete_social_login(request, sociallogin)

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