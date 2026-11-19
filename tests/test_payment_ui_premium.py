"""Payment presentation contract; actual viewport layout requires browser QA."""
import pytest
from django.urls import reverse
from django.templatetags.static import static
from apps.finance.models import Payment
from uuid import uuid4

pytestmark = pytest.mark.django_db


def test_checkout_progress_and_payment_contract(client, customer_user, settings):
    settings.PAYMENT_GATEWAY = "zibal"
    client.force_login(customer_user)
    response = client.get(reverse("finance:topup"))
    assert response.status_code == 200
    html = response.content.decode()
    for token in ("pay-flow--checkout", "pay-checkout-grid", 'name="amount_toman"',
                  'name="payment_nonce"', 'inputmode="numeric"', 'aria-current="step"'):
        assert token in html
    assert static("css/ui-payment.css") in html


@pytest.mark.parametrize("state,css_state", [
    (Payment.Status.VERIFIED, "success"), (Payment.Status.FAILED, "failed"),
    (Payment.Status.REDIRECTED, "pending"), (Payment.Status.CREATED, "pending"),
])
def test_receipt_has_status_specific_action_and_breakable_reference(client, customer_user, state, css_state):
    client.force_login(customer_user)
    payment = Payment.objects.create(customer=customer_user.customer_profile, gateway="zibal",
        amount_irr=123456789012340, provider_amount_irr=123456789012340,
        provider_reference="987654321012345678901234567890", status=state, idempotency_key=str(uuid4()))
    response = client.get(reverse("finance:payment_result", args=[payment.pk]))
    assert response.status_code == 200
    html = response.content.decode()
    assert "pay-result-card--" + css_state in html
    assert 'data-pay-copy="pay-track-id"' in html
    assert "۱۲٬۳۴۵٬۶۷۸٬۹۰۱٬۲۳۴" in html
    assert html.count('aria-current="step"') == 1
    assert ("data-pay-recheck" in html) == (css_state == "pending")
    assert "no-store" in response["Cache-Control"]
