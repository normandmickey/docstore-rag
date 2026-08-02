from django.urls import path

from billing import views

app_name = 'billing'

urlpatterns = [
    path('pricing/', views.pricing, name='pricing'),
    path('', views.billing_page, name='billing'),
    path('checkout/<str:tier>/', views.checkout, name='checkout'),
    path('success/', views.checkout_success, name='checkout_success'),
    path('webhook/', views.stripe_webhook, name='stripe_webhook'),
]