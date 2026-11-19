from django.urls import path

from . import views, zibal_views

app_name = "finance"

urlpatterns = [
    path("wallet/", views.wallet_view, name="wallet"),
    path("wallet/topup/", views.topup_view, name="topup"),
    path("wallet/topup/<uuid:payment_id>/callback/", views.topup_callback, name="topup_callback"),
    path("wallet/topup/<uuid:payment_id>/zibal/return/", zibal_views.zibal_callback, name="zibal_callback"),
    path("wallet/topup/<uuid:payment_id>/start/", zibal_views.payment_start, name="payment_start"),
    path("wallet/topup/<uuid:payment_id>/result/", zibal_views.payment_result, name="payment_result"),
    path("wallet/topup/<uuid:payment_id>/recheck/", zibal_views.payment_recheck, name="payment_recheck"),
    path("transactions/", views.transactions_view, name="transactions"),
    path("invoices/", views.invoices_view, name="invoices"),
    path("invoices/<uuid:invoice_id>/", views.invoice_detail, name="invoice_detail"),
    path("refunds/", views.refunds_view, name="refunds"),
]
