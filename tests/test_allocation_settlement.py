from unittest.mock import patch
from django.utils import timezone
import pytest

from apps.campaigns.models import Campaign, CampaignStatusHistory, TelegramAdvertisement
from apps.finance.models import AdvertisingOrder, WalletLedgerEntry
from apps.finance.services import ensure_wallet, outstanding_order_reservation
from apps.finance.settlement import settle_confirmed_allocation
from apps.telegram_ads.models import APIRequestLog
from tests.test_submission_safety import paid_campaign


@pytest.mark.django_db
@pytest.mark.parametrize("verified", [True, False])
def test_allocation_settlement_is_atomic_and_idempotent(customer_user, verified):
    campaign, order = paid_campaign(customer_user)
    campaign.status = Campaign.Status.AWAITING_TELEGRAM
    campaign.save(update_fields=["status"])
    order.status = AdvertisingOrder.Status.SUBMITTING
    order.save(update_fields=["status"])
    claim = CampaignStatusHistory.objects.create(campaign=campaign, to_status=Campaign.Status.SUBMITTING)
    ad = TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id="123", promotion_url=campaign.destination)
    APIRequestLog.objects.create(operation="create_ad_receipt", success=True, meta={
        "campaign_id": str(campaign.pk), "order_id": str(order.pk), "remote_ad_id": ad.remote_ad_id,
        "idempotency_key": f"tmads-create-{campaign.pk}",
    })
    buffer = order.quote.payload["risk_buffer_irr"]
    with patch("apps.finance.settlement.TelegramAdsClient") as client:
        client.return_value.get_ad.return_value = {"ad_id": 123, "currency": "TON", "promote_url": campaign.destination, "status": "active"}
        client.return_value.get_ad_transactions.return_value = {"total_count": 1, "transactions": [{
            "peer": {"type": "account"}, "currency": "TON", "date": int(claim.created_at.timestamp()),
            "amount": str(order.ton_allocation if verified else order.ton_allocation * 2),
        }]}
        if not verified:
            with pytest.raises(ValueError):
                settle_confirmed_allocation(campaign.pk, actor=customer_user)
            assert outstanding_order_reservation(ensure_wallet(campaign.customer), order.pk) == order.total_irr
            return
        settle_confirmed_allocation(campaign.pk, actor=customer_user)
        settle_confirmed_allocation(campaign.pk, actor=customer_user)
        assert client.return_value.get_ad_transactions.call_count == 1
    wallet = ensure_wallet(campaign.customer)
    order.refresh_from_db()
    assert order.status == AdvertisingOrder.Status.COMPLETED
    assert wallet.available_irr == buffer
    assert wallet.reserved_irr == 0
    assert wallet.ledger_entries.filter(entry_type=WalletLedgerEntry.EntryType.CREDIT_ALLOCATION).count() == 1
