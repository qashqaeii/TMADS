from unittest.mock import patch
from uuid import uuid4

import pytest
from django.urls import reverse
from apps.finance.models import Payment, Invoice
from apps.finance.services import complete_topup_payment, credit_wallet_deposit, ensure_wallet, reserve_for_order, release_reservation_for_order


@pytest.mark.django_db
def test_wallet_release_cannot_use_another_orders_reservation(customer_profile):
    wallet = ensure_wallet(customer_profile)
    credit_wallet_deposit(wallet, 100_000, "seed")
    reserve_for_order(wallet, 80_000, uuid4(), "reserve")
    with pytest.raises(ValueError):
        release_reservation_for_order(wallet, 10_000, uuid4(), "wrong-order")


@pytest.mark.django_db
def test_payment_completion_rolls_back_on_invoice_failure(customer_profile):
    payment = Payment.objects.create(customer=customer_profile, amount_irr=50_000, gateway="fake", idempotency_key="atomic")
    with patch("apps.finance.services.issue_invoice_for_payment", side_effect=RuntimeError("failure")):
        with pytest.raises(RuntimeError):
            complete_topup_payment(payment)
    payment.refresh_from_db()
    assert payment.status != Payment.Status.VERIFIED
    assert ensure_wallet(customer_profile).available_irr == 0
    assert complete_topup_payment(payment)
    assert complete_topup_payment(payment)
    assert ensure_wallet(customer_profile).available_irr == 50_000
    assert Invoice.objects.filter(payment=payment).count() == 1


@pytest.mark.django_db
def test_callback_rejects_wrong_authority_without_provider_call(client, customer_user):
    payment = Payment.objects.create(customer=customer_user.customer_profile, amount_irr=50_000,
        gateway="zarinpal", provider_reference="stored", idempotency_key="authority", status=Payment.Status.REDIRECTED)
    client.force_login(customer_user)
    with patch("apps.finance.views.get_payment_gateway") as gateway:
        client.get(reverse("finance:topup_callback", args=[payment.id]), {"Authority": "different", "Status": "OK"})
        gateway.assert_not_called()
    payment.refresh_from_db()
    assert payment.provider_reference == "stored"
    assert payment.status != Payment.Status.VERIFIED
