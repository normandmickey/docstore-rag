from django.urls import path

from .views import interactions_report, spreadsheet_transform_download, spreadsheet_transformer, support_activity_report

urlpatterns = [
    path('support/', support_activity_report, name='report_support_activity'),
    path('interactions/', interactions_report, name='report_interactions'),
    path('spreadsheet-transformer/', spreadsheet_transformer, name='spreadsheet_transformer'),
    path('spreadsheet-transformer/jobs/<int:job_id>/download/', spreadsheet_transform_download, name='spreadsheet_transform_download'),
]
