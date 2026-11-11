from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("campaigns/", views.campaign_ops, name="campaigns"),
    path("campaigns/<uuid:campaign_id>/", views.campaign_review, name="campaign_review"),
    path("exchange-rates/", views.exchange_rates, name="exchange_rates"),
    path("api-status/", views.api_status, name="api_status"),
    path("audit/", views.audit_logs, name="audit"),
    path("refunds/", views.refunds_ops, name="refunds"),
]
