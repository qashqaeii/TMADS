from unittest.mock import MagicMock, patch
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
    mock_client = MagicMock()
    mock_client.get_ad.return_value = {
        "ad_id": 123, "currency": "TON", "promote_url": campaign.destination, "status": "active",
    }
    with patch("apps.finance.settlement.campaign_client", return_value=mock_client):
        mock_client.get_ad_transactions.return_value = {"total_count": 1, "transactions": [{
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
        assert mock_client.get_ad_transactions.call_count == 1
    wallet = ensure_wallet(campaign.customer)
    order.refresh_from_db()
    assert order.status == AdvertisingOrder.Status.COMPLETED
    assert wallet.available_irr == buffer
    assert wallet.reserved_irr == 0
    assert wallet.ledger_entries.filter(entry_type=WalletLedgerEntry.EntryType.CREDIT_ALLOCATION).count() == 1


@pytest.mark.django_db
def test_settlement_rejects_mismatched_remote_account(customer_user):
    campaign, order = paid_campaign(customer_user)
    campaign.status = Campaign.Status.AWAITING_TELEGRAM
    campaign.save(update_fields=["status"])
    order.status = AdvertisingOrder.Status.SUBMITTING
    order.save(update_fields=["status"])
    CampaignStatusHistory.objects.create(campaign=campaign, to_status=Campaign.Status.SUBMITTING)
    ad = TelegramAdvertisement.objects.create(
        campaign=campaign, remote_ad_id="123", remote_account_id="wrong-account",
        promotion_url=campaign.destination,
    )
    APIRequestLog.objects.create(
        operation="create_ad_receipt", success=True,
        meta={
            "campaign_id": str(campaign.pk), "order_id": str(order.pk),
            "remote_ad_id": ad.remote_ad_id, "idempotency_key": f"tmads-create-{campaign.pk}",
        },
    )
    from apps.telegram_ads.models import RelatedAccountRequest, TelegramAdsConnection

    row = RelatedAccountRequest.objects.create(
        customer=customer_user.customer_profile,
        status=RelatedAccountRequest.Status.PROVISIONED,
        title="Child",
        consent_at=timezone.now(),
        main_account_id="main-1",
        remote_account_id="expected-child",
    )
    connection = TelegramAdsConnection.objects.create(
        customer=customer_user.customer_profile,
        connection_type=TelegramAdsConnection.Type.PLATFORM_MANAGED,
        status=TelegramAdsConnection.Status.CONNECTED,
        remote_account_id="expected-child",
        related_account=row,
        currency="TON",
        remaining_budget=0,
        is_default=True,
    )
    campaign.telegram_connection = connection
    campaign.save(update_fields=["telegram_connection"])
    with patch("apps.finance.settlement.campaign_client") as client_factory:
        mock = client_factory.return_value
        mock.get_ad.return_value = {
            "ad_id": 123, "currency": "TON", "promote_url": campaign.destination, "status": "active",
        }
        with pytest.raises(ValueError, match="حساب"):
            settle_confirmed_allocation(campaign.pk, actor=customer_user)


@pytest.mark.django_db
@pytest.mark.parametrize("changed", ["destination", "fee", "quote", "account", "campaign", "receipt", "claim", "extra_ad"])
def test_settlement_rejects_changed_context_after_evidence(customer_user, changed):
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
    client = MagicMock()
    client.get_ad.return_value = {
        "ad_id": 123, "currency": "TON", "promote_url": campaign.destination, "status": "active",
    }

    def evidence(*args, **kwargs):
        if changed == "destination":
            Campaign.objects.filter(pk=campaign.pk).update(destination="https://t.me/changed")
        elif changed == "fee":
            AdvertisingOrder.objects.filter(pk=order.pk).update(service_fee_irr=order.service_fee_irr + 1)
        elif changed == "quote":
            quote = order.quote
            quote.payload["risk_buffer_irr"] += 1
            quote.save(update_fields=["payload"])
        elif changed == "account":
            TelegramAdvertisement.objects.filter(pk=ad.pk).update(remote_account_id="changed")
        elif changed == "receipt":
            APIRequestLog.objects.filter(operation="create_ad_receipt", meta__campaign_id=str(campaign.pk)).update(success=False)
        elif changed == "claim":
            CampaignStatusHistory.objects.filter(pk=claim.pk).delete()
        elif changed == "extra_ad":
            TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id="456", promotion_url=campaign.destination)
        else:
            from uuid import uuid4
            AdvertisingOrder.objects.filter(pk=order.pk).update(campaign_id=uuid4())
        return {"total_count": 1, "transactions": [{
            "peer": {"type": "account"}, "currency": "TON", "date": int(claim.created_at.timestamp()),
            "amount": str(order.ton_allocation),
        }]}

    client.get_ad_transactions.side_effect = evidence
    with patch("apps.finance.settlement.campaign_client", return_value=client):
        with pytest.raises(ValueError):
            settle_confirmed_allocation(campaign.pk, actor=customer_user)
    order.refresh_from_db()
    wallet = ensure_wallet(campaign.customer)
    assert order.status == AdvertisingOrder.Status.SUBMITTING
    assert outstanding_order_reservation(wallet, order.pk) == order.total_irr
    assert not wallet.ledger_entries.filter(entry_type=WalletLedgerEntry.EntryType.CREDIT_ALLOCATION).exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_allocation_settlement_postgresql(customer_user):
    """Both workers obtain evidence before either can consume the reservation."""
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from django.db import connection, connections, close_old_connections

    if connection.vendor != "postgresql":
        pytest.skip("Requires PostgreSQL row-level locking")
    campaign, order = paid_campaign(customer_user)
    campaign.status = Campaign.Status.AWAITING_TELEGRAM
    campaign.save(update_fields=["status"])
    order.status = AdvertisingOrder.Status.SUBMITTING
    order.save(update_fields=["status"])
    claim = CampaignStatusHistory.objects.create(
        campaign=campaign, to_status=Campaign.Status.SUBMITTING,
    )
    ad = TelegramAdvertisement.objects.create(
        campaign=campaign, remote_ad_id="123", promotion_url=campaign.destination,
    )
    APIRequestLog.objects.create(operation="create_ad_receipt", success=True, meta={
        "campaign_id": str(campaign.pk), "order_id": str(order.pk),
        "remote_ad_id": ad.remote_ad_id, "idempotency_key": f"tmads-create-{campaign.pk}",
    })
    barrier = Barrier(2, timeout=15)
    buffer = order.quote.payload["risk_buffer_irr"]
    client = MagicMock()
    client.get_ad.return_value = {
        "ad_id": 123, "currency": "TON", "promote_url": campaign.destination, "status": "active",
    }

    def evidence(*args, **kwargs):
        barrier.wait()
        return {"total_count": 1, "transactions": [{
            "peer": {"type": "account"}, "currency": "TON",
            "date": int(claim.created_at.timestamp()), "amount": str(order.ton_allocation),
        }]}

    client.get_ad_transactions.side_effect = evidence

    def worker():
        close_old_connections()
        try:
            with connections["default"].cursor() as cursor:
                cursor.execute("SET lock_timeout = '10s'")
            return settle_confirmed_allocation(campaign.pk, actor=customer_user).pk
        finally:
            connections.close_all()

    with patch("apps.finance.settlement.campaign_client", return_value=client):
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            assert [future.result(timeout=30) for future in futures] == [order.pk, order.pk]
    assert client.get_ad_transactions.call_count == 2
    order.refresh_from_db()
    wallet = ensure_wallet(campaign.customer)
    assert order.status == AdvertisingOrder.Status.COMPLETED
    assert wallet.available_irr == buffer
    assert wallet.reserved_irr == 0
    assert outstanding_order_reservation(wallet, order.pk) == 0
    entries = wallet.ledger_entries.filter(related_order_id=order.pk)
    assert entries.filter(entry_type=WalletLedgerEntry.EntryType.CREDIT_ALLOCATION).count() == 1
    assert entries.filter(entry_type=WalletLedgerEntry.EntryType.SERVICE_FEE).count() == int(order.service_fee_irr > 0)
    from apps.core.models import AuditLog
    assert AuditLog.objects.filter(action="order.allocation_settled", entity_id=order.pk).count() == 1
