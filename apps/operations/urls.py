from django.urls import path

from . import views, account_reports, release_views, sms_views, funding_views
from apps.telegram_ads.related_views import ops_related_accounts
from apps.telegram_ads.platform_token_views import platform_api_token
from apps.campaigns.remote_views import remote_operations

app_name = "operations"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("remote-operations/", remote_operations, name="remote_operations"),
    path("campaigns/", views.campaign_ops, name="campaigns"),
    path("campaigns/<uuid:campaign_id>/", views.campaign_review, name="campaign_review"),
    path("exchange-rates/", views.exchange_rates, name="exchange_rates"),
    path("related-accounts/", ops_related_accounts, name="related_accounts"),
    path("telegram-account/", account_reports.account_workspace, name="telegram_account"),
    path("telegram-account/credentials/", platform_api_token, name="platform_api_token"),
    path("sms/", sms_views.sms_workspace, name="sms"),
    path("api-status/", views.api_status, name="api_status"),
    path("release-readiness/", release_views.release_readiness, name="release_readiness"),
    path("audit/", views.audit_logs, name="audit"),
    path("refunds/", views.refunds_ops, name="refunds"),
    path("funding-transfers/", funding_views.funding_transfers_ops, name="funding_transfers"),
]
