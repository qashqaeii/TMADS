from unittest.mock import patch
import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from apps.finance.gateways.zarinpal import ZarinpalGateway
from apps.finance.models import Payment


def test_zarinpal_uses_explicit_rial_for_request_and_verification(settings):
    settings.ZARINPAL_MERCHANT_ID = "mock-only"
    with patch("apps.finance.gateways.zarinpal.httpx.Client") as client:
        post = client.return_value.__enter__.return_value.post
        post.return_value.json.return_value = {"data": {"code": 100, "authority": "mock-authority"}}
        gateway = ZarinpalGateway()
        assert gateway.create_payment(amount_irr=100000, callback_url="https://example.test/callback", description="test").success
        sent = post.call_args.kwargs["json"]
        assert sent["amount"] == 100000 and sent["currency"] == "IRR"
        assert gateway.verify_payment(provider_reference="mock-authority", amount_irr=100000).success
        assert post.call_args.kwargs["json"]["amount"] == 100000


@pytest.mark.django_db
def test_provider_reference_cannot_be_reused(customer_profile):
    kwargs = {"customer": customer_profile, "gateway": "zarinpal", "amount_irr": 100000, "provider_reference": "same"}
    Payment.objects.create(**kwargs, idempotency_key="a")
    with pytest.raises(IntegrityError), transaction.atomic():
        Payment.objects.create(**kwargs, idempotency_key="b")


@pytest.mark.django_db
def test_legacy_payment_not_reinterpreted(client, customer_user):
    payment = Payment.objects.create(customer=customer_user.customer_profile, gateway="zarinpal",
        amount_irr=100000, status=Payment.Status.REDIRECTED, provider_reference="legacy", idempotency_key="legacy")
    client.force_login(customer_user)
    with patch("apps.finance.views.get_payment_gateway") as gateway:
        client.get(reverse("finance:topup_callback", args=[payment.pk]), {"Authority":"legacy", "Status":"OK"})
        gateway.assert_not_called()
    payment.refresh_from_db()
    assert payment.status == Payment.Status.REDIRECTED
