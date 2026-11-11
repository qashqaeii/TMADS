import pytest

from apps.finance.models import Invoice, Payment
from apps.finance.services import ensure_wallet, verify_fake_payment


@pytest.mark.django_db
def test_fake_payment_issues_invoice(customer_profile):
    wallet = ensure_wallet(customer_profile)
    payment = Payment.objects.create(
        customer=customer_profile,
        amount_irr=50_000,
        gateway="fake",
        provider_reference="demo-ref",
        idempotency_key="pay-invoice-1",
    )
    assert verify_fake_payment(payment)
    wallet.refresh_from_db()
    assert wallet.available_irr == 50_000
    assert Invoice.objects.filter(payment=payment).count() == 1
