from django.urls import path

from .views import support_activity_report

urlpatterns = [
    path('support/', support_activity_report, name='report_support_activity'),
]
