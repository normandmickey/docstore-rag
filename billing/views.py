import json
import logging

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from billing.models import (
    PLAN_LIMITS,
    STRIPE_PRICES,
    Subscription,
    TIER_BUSINESS,
    TIER_FREE,
    TIER_PRO,
)
from control.models import Tenant

logger = logging.getLogger(__name__)


def get_or_create_subscription(tenant):
    """Get existing subscription or create a free one for the tenant."""
    sub, created = Subscription.objects.get_or_create(
        tenant=tenant,
        defaults={'tier': TIER_FREE, 'status': Subscription.STATUS_ACTIVE},
    )
    return sub


def get_tenant(request):
    """Get the current tenant from session."""
    tenant_id = request.session.get('current_tenant_id')
    if not tenant_id or not request.user.is_authenticated:
        return None
    try:
        return Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        return None


def pricing(request):
    """Public pricing page."""
    return render(request, 'billing/pricing.html', {
        'plans': [
            {'tier': TIER_FREE, 'name': 'Free', 'price': 0, 'limits': PLAN_LIMITS[TIER_FREE]},
            {'tier': TIER_PRO, 'name': 'Pro', 'price': 29, 'limits': PLAN_LIMITS[TIER_PRO]},
            {'tier': TIER_BUSINESS, 'name': 'Business', 'price': 99, 'limits': PLAN_LIMITS[TIER_BUSINESS]},
        ],
    })


@login_required
def billing_page(request):
    """Billing dashboard page — shows current plan, usage, and upgrade options."""
    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')

    sub = get_or_create_subscription(tenant)
    sub.reset_monthly_usage_if_needed()

    return render(request, 'billing/billing.html', {
        'subscription': sub,
        'plans': [
            {'tier': TIER_FREE, 'name': 'Free', 'price': 0, 'limits': PLAN_LIMITS[TIER_FREE]},
            {'tier': TIER_PRO, 'name': 'Pro', 'price': 29, 'limits': PLAN_LIMITS[TIER_PRO]},
            {'tier': TIER_BUSINESS, 'name': 'Business', 'price': 99, 'limits': PLAN_LIMITS[TIER_BUSINESS]},
        ],
    })


@login_required
def checkout(request, tier):
    """Redirect to Stripe Checkout for the selected tier."""
    if tier not in (TIER_PRO, TIER_BUSINESS):
        return redirect('billing')

    tenant = get_tenant(request)
    if not tenant:
        return redirect('dashboard')

    sub = get_or_create_subscription(tenant)

    stripe.api_key = settings.STRIPE_SECRET_KEY

    # Create or reuse Stripe customer
    customer_kwargs = {}
    if sub.stripe_customer_id:
        customer_kwargs['customer'] = sub.stripe_customer_id
    else:
        customer = stripe.Customer.create(
            email=request.user.email or request.user.username,
            name=tenant.name,
            metadata={'tenant_id': tenant.id, 'tenant_slug': tenant.slug},
        )
        sub.stripe_customer_id = customer.id
        sub.save(update_fields=['stripe_customer_id'])
        customer_kwargs['customer'] = customer.id

    price_id = STRIPE_PRICES.get(tier, '')
    if not price_id:
        # No Stripe price configured yet — show a message
        from django.contrib import messages
        messages.error(request, f'Stripe pricing for the {tier} plan is not configured yet. Please contact support.')
        return redirect('billing')

    session = stripe.checkout.Session.create(
        mode='subscription',
        line_items=[{'price': price_id, 'quantity': 1}],
        success_url=settings.SITE_URL + '/billing/success/',
        cancel_url=settings.SITE_URL + '/billing/',
        metadata={
            'tenant_id': tenant.id,
            'tier': tier,
        },
        subscription_data={
            'metadata': {
                'tenant_id': tenant.id,
                'tier': tier,
            },
        },
    )

    return redirect(session.url)


@login_required
def checkout_success(request):
    """Stripe Checkout success redirect — show confirmation."""
    return render(request, 'billing/success.html')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Handle Stripe webhook events."""
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

    if endpoint_secret:
        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.warning('Stripe webhook signature verification failed: %s', e)
            return HttpResponse(status=400)
    else:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            return HttpResponse(status=400)

    event_type = event.get('type', '')
    data = event.get('data', {}).get('object', {})

    logger.info('Stripe webhook: %s', event_type)

    if event_type == 'checkout.session.completed':
        _handle_checkout_completed(data)
    elif event_type == 'customer.subscription.created':
        _handle_subscription_created(data)
    elif event_type == 'customer.subscription.updated':
        _handle_subscription_updated(data)
    elif event_type == 'customer.subscription.deleted':
        _handle_subscription_deleted(data)
    elif event_type == 'invoice.payment_succeeded':
        _handle_invoice_paid(data)

    return HttpResponse(status=200)


def _get_tenant_from_stripe(data):
    """Extract tenant from Stripe metadata or customer ID."""
    metadata = data.get('metadata', {})
    tenant_id = metadata.get('tenant_id')
    if tenant_id:
        try:
            return Tenant.objects.get(id=tenant_id)
        except (Tenant.DoesNotExist, ValueError):
            pass

    # Try via customer → subscription metadata
    customer_id = data.get('customer', '')
    if customer_id:
        try:
            sub = Subscription.objects.get(stripe_customer_id=customer_id)
            return sub.tenant
        except Subscription.DoesNotExist:
            pass

    return None


def _handle_checkout_completed(data):
    tenant_id = data.get('metadata', {}).get('tenant_id')
    tier = data.get('metadata', {}).get('tier')
    customer_id = data.get('customer', '')
    subscription_id = data.get('subscription', '')

    if not tenant_id:
        return

    try:
        tenant = Tenant.objects.get(id=tenant_id)
    except Tenant.DoesNotExist:
        logger.warning('Stripe checkout: tenant %s not found', tenant_id)
        return

    sub = get_or_create_subscription(tenant)
    sub.stripe_customer_id = customer_id
    sub.stripe_subscription_id = subscription_id
    if tier in (TIER_PRO, TIER_BUSINESS):
        sub.tier = tier
    sub.status = Subscription.STATUS_ACTIVE
    sub.save()


def _handle_subscription_created(data):
    tenant = _get_tenant_from_stripe(data)
    if not tenant:
        return
    sub = get_or_create_subscription(tenant)
    sub.stripe_subscription_id = data.get('id', '')
    sub.stripe_customer_id = data.get('customer', '')
    sub.stripe_price_id = (data.get('items', {}).get('data', [{}])[0].get('price', {}).get('id', ''))
    sub.status = data.get('status', Subscription.STATUS_ACTIVE)
    sub.current_period_start = timezone.datetime.fromtimestamp(data.get('current_period_start', 0)) if data.get('current_period_start') else None
    sub.current_period_end = timezone.datetime.fromtimestamp(data.get('current_period_end', 0)) if data.get('current_period_end') else None
    sub.save()


def _handle_subscription_updated(data):
    tenant = _get_tenant_from_stripe(data)
    if not tenant:
        return
    sub = get_or_create_subscription(tenant)
    sub.stripe_subscription_id = data.get('id', '')
    sub.status = data.get('status', sub.status)
    sub.cancel_at_period_end = data.get('cancel_at_period_end', False)
    sub.current_period_start = timezone.datetime.fromtimestamp(data.get('current_period_start', 0)) if data.get('current_period_start') else None
    sub.current_period_end = timezone.datetime.fromtimestamp(data.get('current_period_end', 0)) if data.get('current_period_end') else None

    # Update tier from price
    price_id = (data.get('items', {}).get('data', [{}])[0].get('price', {}).get('id', ''))
    if price_id:
        sub.stripe_price_id = price_id
        # Map price ID back to tier
        for tier, pid in STRIPE_PRICES.items():
            if pid == price_id:
                sub.tier = tier
                break

    # If subscription was canceled, downgrade to free
    if data.get('status') == 'canceled':
        sub.tier = TIER_FREE

    sub.save()


def _handle_subscription_deleted(data):
    tenant = _get_tenant_from_stripe(data)
    if not tenant:
        return
    sub = get_or_create_subscription(tenant)
    sub.tier = TIER_FREE
    sub.status = Subscription.STATUS_CANCELED
    sub.save()


def _handle_invoice_paid(data):
    # Reset usage on successful payment
    customer_id = data.get('customer', '')
    if not customer_id:
        return
    try:
        sub = Subscription.objects.get(stripe_customer_id=customer_id)
        sub.queries_this_month = 0
        sub.usage_period_start = timezone.now()
        sub.save(update_fields=['queries_this_month', 'usage_period_start'])
    except Subscription.DoesNotExist:
        pass