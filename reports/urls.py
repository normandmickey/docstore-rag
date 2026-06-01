from django.urls import path

from .views import interactions_report, spreadsheet_transformer, support_activity_report

urlpatterns = [
    path('support/', support_activity_report, name='report_support_activity'),
    path('interactions/', interactions_report, name='report_interactions'),
    path('spreadsheet-transformer/', spreadsheet_transformer, name='spreadsheet_transformer'),
]
