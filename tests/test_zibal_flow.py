"""End-to-end Django Zibal wallet flow using a mocked provider."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4
import pytest
from django.core.management import call_command
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User
from apps.finance.gateways.base import GatewayResult
from apps.finance.models import Payment, PaymentVerification, Invoice
from apps.finance.services import ensure_wallet
from apps.finance.zibal_views import callback_url, verify_zibal

pytestmark = pytest.mark.django_db
AMOUNT = 120000
TRACK = "45123"


@pytest.fixture
def pending(customer_profile):
    return Payment.objects.create(customer=customer_profile, amount_irr=AMOUNT,
        gateway="zibal", provider_amount_irr=AMOUNT, provider_reference=TRACK,
        status=Payment.Status.REDIRECTED, idempotency_key=str(uuid4()))


def successful():
    return GatewayResult(True, TRACK, {"code": 100, "paid_amount_irr": AMOUNT, "bank_reference": "123456"})


def path(name, payment):
    return reverse("finance:" + name, args=[payment.pk])


def callback(client, payment, **kwargs):
    return client.get(path("zibal_callback", payment), {"trackId": TRACK, "success": "1",
                      "orderId": str(payment.pk), **kwargs})


def test_checkout_idempotent_and_handoff(client, customer_user, settings):
    settings.PAYMENT_GATEWAY = "zibal"
    client.force_login(customer_user)
    url = reverse("finance:topup")
    assert client.get(url).status_code == 200
    data = {"amount_toman": "12000", "payment_nonce": str(uuid4())}
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        request = gateway.return_value.create_payment
        request.return_value = GatewayResult(True, TRACK, {})
        first = client.post(url, data)
        second = client.post(url, data)
        request.assert_called_once()
        assert request.call_args.kwargs["amount_irr"] == AMOUNT
        assert "/zibal/return/" in request.call_args.kwargs["callback_url"]
    payment = Payment.objects.get(gateway="zibal")
    assert first.url == second.url == path("payment_start", payment)
    handoff = client.get(first.url)
    assert handoff.status_code == 200
    assert b"https://gateway.zibal.ir/start/45123" in handoff.content
    assert "no-store" in handoff["Cache-Control"]


def test_failed_request_does_not_credit(client, customer_user, settings):
    settings.PAYMENT_GATEWAY = "zibal"
    client.force_login(customer_user)
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        gateway.return_value.create_payment.return_value = GatewayResult(False, raw={"code": 103})
        response = client.post(reverse("finance:topup"), {"amount_toman": "12000", "payment_nonce": str(uuid4())})
    payment = Payment.objects.get(gateway="zibal")
    assert payment.status == Payment.Status.FAILED
    assert client.get(response.url).status_code == 200
    assert ensure_wallet(customer_user.customer_profile).available_irr == 0


def test_callback_without_session_once_only_and_private_receipt(client, pending, customer_user):
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        gateway.return_value.verify_payment.return_value = successful()
        assert callback(client, pending).status_code == 302
        assert callback(client, pending).status_code == 302
        gateway.return_value.verify_payment.assert_called_once()
    pending.refresh_from_db()
    assert pending.status == Payment.Status.VERIFIED
    assert ensure_wallet(pending.customer).available_irr == AMOUNT
    assert Invoice.objects.filter(payment=pending).count() == 1
    assert PaymentVerification.objects.filter(payment=pending, success=True).count() == 1
    assert client.get(path("payment_result", pending)).status_code == 302
    client.force_login(customer_user)
    receipt = client.get(path("payment_result", pending))
    assert receipt.status_code == 200 and b"123456" in receipt.content
    assert "no-store" in receipt["Cache-Control"]


@pytest.mark.parametrize("params", [{"trackId": "999"}, {"orderId": "wrong"}, {"trackId": ""}])
def test_forged_callback_never_reaches_gateway(client, pending, params):
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        callback(client, pending, **params)
        gateway.assert_not_called()
    pending.refresh_from_db()
    assert pending.status == Payment.Status.REDIRECTED
    assert ensure_wallet(pending.customer).available_irr == 0


def test_cross_customer_result_start_and_recheck_are_private(client, pending):
    other = User.objects.create_user(username="other-zibal", password="pass1234", role=User.Role.CUSTOMER)
    client.force_login(other)
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        assert client.get(path("payment_result", pending)).status_code == 404
        assert client.get(path("payment_start", pending)).status_code == 404
        assert client.post(path("payment_recheck", pending)).status_code == 404
        gateway.assert_not_called()


@pytest.mark.parametrize("response", [
    GatewayResult(False, TRACK, {"code": 202}),
    GatewayResult(False, TRACK, {"error": "gateway_unavailable"}),
    GatewayResult(True, TRACK, {"paid_amount_irr": AMOUNT+1, "bank_reference": "123"}),
    GatewayResult(True, "999", {"paid_amount_irr": AMOUNT, "bank_reference": "123"}),
    GatewayResult(True, TRACK, {"paid_amount_irr": AMOUNT}),
])
def test_uncertain_or_invalid_verify_never_credits(client, pending, response):
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        gateway.return_value.verify_payment.return_value = response
        callback(client, pending, success="0")
    pending.refresh_from_db()
    assert pending.status == Payment.Status.REDIRECTED
    assert not Invoice.objects.filter(payment=pending).exists()
    assert ensure_wallet(pending.customer).available_irr == 0
    assert pending.verifications.filter(success=False).count() == 1


def test_recheck_after_timeout_and_cooldown(client, pending, customer_user):
    client.force_login(customer_user)
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        verify = gateway.return_value.verify_payment
        verify.side_effect = [GatewayResult(False, TRACK, {"error": "gateway_unavailable"}), successful()]
        callback(client, pending)
        client.post(path("payment_recheck", pending))
        assert verify.call_count == 1
        pending.verifications.update(created_at=timezone.now()-timedelta(seconds=30))
        assert client.get(path("payment_recheck", pending)).status_code == 405
        assert client.post(path("payment_recheck", pending)).status_code == 302
        assert verify.call_count == 2
    pending.refresh_from_db()
    assert pending.status == Payment.Status.VERIFIED
    assert ensure_wallet(pending.customer).available_irr == AMOUNT


def test_invoice_failure_rolls_back_and_next_verify_can_recover(pending):
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        gateway.return_value.verify_payment.return_value = successful()
        with patch("apps.finance.services.issue_invoice_for_payment", side_effect=RuntimeError("failure")):
            with pytest.raises(RuntimeError):
                verify_zibal(pending.pk, expected_track=TRACK)
        pending.refresh_from_db()
        assert pending.status == Payment.Status.REDIRECTED
        assert not pending.verifications.exists()
        assert ensure_wallet(pending.customer).available_irr == 0
        verify_zibal(pending.pk, expected_track=TRACK)
    assert ensure_wallet(pending.customer).available_irr == AMOUNT
    assert Invoice.objects.filter(payment=pending).count() == 1


def test_legacy_amount_mismatch_prevents_provider_call(pending):
    pending.provider_amount_irr = AMOUNT+1
    pending.save(update_fields=["provider_amount_irr"])
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        verify_zibal(pending.pk, expected_track=TRACK)
        gateway.assert_not_called()


@pytest.mark.parametrize("origin,expected", [("https://tmads.example", True), ("", False),
    ("http://tmads.example", False), ("https://localhost", False), ("https://tmads.example/path", False)])
def test_production_callback_uses_configured_https_origin(settings, pending, origin, expected):
    settings.APP_ENV = "PRODUCTION"
    settings.PUBLIC_SITE_URL = origin
    result = callback_url(RequestFactory().get("/"), pending.pk)
    assert bool(result) is expected
    if expected:
        assert result == origin + path("zibal_callback", pending)


def test_operator_reconciliation_dry_run_does_not_touch_provider(pending):
    with patch("apps.finance.zibal_views.get_payment_gateway") as gateway:
        out = StringIO()
        call_command("reconcile_zibal", payment_id=str(pending.pk), stdout=out)
        assert "Dry run" in out.getvalue()
        gateway.assert_not_called()
