from django.urls import path

from . import views, account_reports
from apps.campaigns.remote_views import remote_operations

app_name = "operations"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("remote-operations/", remote_operations, name="remote_operations"),
    path("campaigns/", views.campaign_ops, name="campaigns"),
    path("campaigns/<uuid:campaign_id>/", views.campaign_review, name="campaign_review"),
    path("exchange-rates/", views.exchange_rates, name="exchange_rates"),
    path("telegram-account/", account_reports.account_workspace, name="telegram_account"),
    path("api-status/", views.api_status, name="api_status"),
    path("audit/", views.audit_logs, name="audit"),
    path("refunds/", views.refunds_ops, name="refunds"),
]
