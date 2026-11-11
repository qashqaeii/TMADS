import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.campaigns.models import Campaign
from apps.campaigns.views import _create_quote
from apps.finance.models import RefundRequest
from apps.finance.refunds import approve_refund, create_refund_request
from apps.finance.services import credit_wallet_deposit, ensure_wallet, reserve_for_order


@pytest.mark.django_db
def test_refund_releases_reservation(customer_user):
    wallet = ensure_wallet(customer_user.customer_profile)
    credit_wallet_deposit(wallet, 3_000_000, "refund-seed")
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="refund-c",
        status=Campaign.Status.AWAITING_PAYMENT,
        budget_irr=500_000,
        wizard_step=8,
    )
    _create_quote(campaign)
    from apps.finance.models import AdvertisingOrder

    order = AdvertisingOrder.objects.get(campaign_id=campaign.id)
    reserve_for_order(wallet, order.total_irr, order.id, f"res-{order.id}")
    order.status = AdvertisingOrder.Status.PAID
    order.save(update_fields=["status"])
    campaign.status = Campaign.Status.PENDING_REVIEW
    campaign.save(update_fields=["status"])

    refund = create_refund_request(customer=customer_user.customer_profile, order=order, reason="تست")
    staff = User.objects.create_user(username="ops1", password="pass1234", role=User.Role.ADMIN)
    approve_refund(refund, actor=staff)

    wallet.refresh_from_db()
    order.refresh_from_db()
    assert refund.status == RefundRequest.Status.PAID
    assert order.status == AdvertisingOrder.Status.CANCELLED
    assert wallet.reserved_irr == 0
    assert wallet.available_irr == 3_000_000


@pytest.mark.django_db
def test_refunds_page_requires_login(client):
    url = reverse("finance:refunds")
    assert client.get(url).status_code == 302
