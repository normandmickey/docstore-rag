import logging

from billing.models import TIER_FREE, Subscription
from control.models import Tenant

logger = logging.getLogger(__name__)

# Paths that don't require subscription checks
EXEMPT_PATHS = (
    '/healthz/',
    '/login/',
    '/logout/',
    '/signup/',
    '/accounts/',
    '/admin/',
    '/api/schema/',
    '/api/docs/',
    '/privacy/',
    '/terms/',
    '/offline/',
    '/sw.js',
    '/manifest.webmanifest',
    '/static/',
    '/media/',
    '/billing/pricing/',
    '/billing/webhook/',
    '/billing/checkout/',
    '/billing/success/',
)

# API paths that need different handling (return JSON instead of redirect)
API_PREFIX = '/api/'


class SubscriptionMiddleware:
    """Enforce subscription tier limits on dashboard and API access."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for exempt paths
        if any(request.path.startswith(p) for p in EXEMPT_PATHS):
            return self.get_response(request)

        # Skip for unauthenticated users (let auth middleware handle redirect)
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Get tenant from session
        tenant_id = request.session.get('current_tenant_id')
        if not tenant_id:
            return self.get_response(request)

        try:
            tenant = Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            return self.get_response(request)

        # Get or create subscription
        sub, _ = Subscription.objects.get_or_create(
            tenant=tenant,
            defaults={'tier': TIER_FREE, 'status': Subscription.STATUS_ACTIVE},
        )

        # Attach subscription to request for views to use
        request.subscription = sub

        return self.get_response(request)


def check_limits(request, limit_key, current_count=0):
    """
    Utility function for views to check if a limit is exceeded.
    Returns (exceeded, limit_value).
    """
    sub = getattr(request, 'subscription', None)
    if not sub:
        return False, 0

    limits = sub.limits
    limit = limits.get(limit_key, 0)

    # 0 means unlimited
    if limit == 0:
        return False, 0

    return current_count >= limit, limit


def increment_usage(request):
    """Increment query usage for the current tenant's subscription."""
    sub = getattr(request, 'subscription', None)
    if not sub:
        return

    sub.reset_monthly_usage_if_needed()
    sub.queries_this_month += 1
    sub.save(update_fields=['queries_this_month'])