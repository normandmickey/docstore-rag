from django.conf import settings
from django.db import models
from django.utils import timezone

from control.models import Tenant

User = settings.AUTH_USER_MODEL

TIER_FREE = 'free'
TIER_PRO = 'pro'
TIER_BUSINESS = 'business'
TIER_CHOICES = [
    (TIER_FREE, 'Free'),
    (TIER_PRO, 'Pro'),
    (TIER_BUSINESS, 'Business'),
]

# Plan limits keyed by tier
PLAN_LIMITS = {
    TIER_FREE: {
        'max_workspaces': 1,
        'max_documents': 25,
        'max_queries_per_month': 100,
        'max_connectors': 1,
        'max_chatbots': 0,
        'max_support_channels': 0,
        'api_access': False,
        'voice_agent': False,
    },
    TIER_PRO: {
        'max_workspaces': 5,
        'max_documents': 500,
        'max_queries_per_month': 5000,
        'max_connectors': 3,
        'max_chatbots': 2,
        'max_support_channels': 2,
        'api_access': True,
        'voice_agent': False,
    },
    TIER_BUSINESS: {
        'max_workspaces': 0,  # 0 = unlimited
        'max_documents': 10000,
        'max_queries_per_month': 50000,
        'max_connectors': 0,  # 0 = unlimited
        'max_chatbots': 0,
        'max_support_channels': 0,
        'api_access': True,
        'voice_agent': True,
    },
}

# Stripe price IDs (filled in from env or admin)
STRIPE_PRICES = {
    TIER_PRO: settings.STRIPE_PRO_PRICE_ID,
    TIER_BUSINESS: settings.STRIPE_BUSINESS_PRICE_ID,
}


class Subscription(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_TRIALING = 'trialing'
    STATUS_PAST_DUE = 'past_due'
    STATUS_CANCELED = 'canceled'
    STATUS_INCOMPLETE = 'incomplete'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_TRIALING, 'Trialing'),
        (STATUS_PAST_DUE, 'Past Due'),
        (STATUS_CANCELED, 'Canceled'),
        (STATUS_INCOMPLETE, 'Incomplete'),
    ]

    tenant = models.OneToOneField(Tenant, on_delete=models.CASCADE, related_name='subscription')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default=TIER_FREE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)

    stripe_customer_id = models.CharField(max_length=255, blank=True, default='')
    stripe_subscription_id = models.CharField(max_length=255, blank=True, default='')
    stripe_price_id = models.CharField(max_length=255, blank=True, default='')

    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)

    # Monthly usage tracking
    queries_this_month = models.PositiveIntegerField(default=0)
    usage_period_start = models.DateTimeField(default=timezone.now)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.tenant.name} — {self.tier} ({self.status})'

    @property
    def is_active(self):
        return self.status in (self.STATUS_ACTIVE, self.STATUS_TRIALING)

    @property
    def limits(self):
        return PLAN_LIMITS.get(self.tier, PLAN_LIMITS[TIER_FREE])

    def reset_monthly_usage_if_needed(self):
        """Reset query counter if we're in a new month."""
        now = timezone.now()
        if self.usage_period_start.month != now.month or self.usage_period_start.year != now.year:
            self.queries_this_month = 0
            self.usage_period_start = now
            self.save(update_fields=['queries_this_month', 'usage_period_start'])