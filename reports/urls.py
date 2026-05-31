from django.urls import path

from .views import interactions_report, support_activity_report

urlpatterns = [
    path('support/', support_activity_report, name='report_support_activity'),
    path('interactions/', interactions_report, name='report_interactions'),
]
