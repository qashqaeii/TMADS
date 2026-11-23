import pytest
from datetime import datetime, timezone as dt_timezone
from unittest.mock import MagicMock

from apps.accounts.models import User
from apps.campaigns.models import Campaign, CampaignStatisticsSnapshot, TelegramAdvertisement
from apps.telegram_ads.services.sync import sync_ad_statistics_for


@pytest.mark.django_db
def test_sync_ad_statistics_stores_period_rows(monkeypatch):
    user = User.objects.create_user(username="syncu", password="x")
    customer = user.customer_profile
    campaign = Campaign.objects.create(customer=customer, name="T", status=Campaign.Status.ACTIVE)
    ad = TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id="42")

    ts = int(datetime(2026, 1, 5, tzinfo=dt_timezone.utc).timestamp())
    fake_items = [{"from_time": ts, "views": 10, "clicks": 2, "actions": 1, "spent_budget": "0.1", "currency": "TON"}]

    class FakeClient:
        def get_ad_statistics(self, *args, **kwargs):
            return {"items": fake_items}

    monkeypatch.setattr(
        "apps.telegram_ads.services.sync.campaign_client",
        lambda campaign: FakeClient(),
    )

    n = sync_ad_statistics_for(ad, days=7)
    assert n == 1
    snap = CampaignStatisticsSnapshot.objects.get(advertisement=ad)
    assert snap.impressions == 10
    assert snap.raw.get("kind") == "period"

    assert snap.raw["spent_verified"] is True


@pytest.mark.django_db
def test_remote_sync_preserves_unknown_status_and_financial_lock():
    from apps.telegram_ads.services.sync import _sync_campaign_from_remote
    from apps.finance.models import AdvertisingOrder
    user = User.objects.create_user(username="sync-safe", password="x")
    campaign = Campaign.objects.create(customer=user.customer_profile, name="T", status=Campaign.Status.ACTIVE)
    ad = TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id="47", remote_status_raw={"status": "unknown"})
    _sync_campaign_from_remote(ad)
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.ACTIVE
    campaign.status = Campaign.Status.RECONCILIATION
    campaign.save(update_fields=["status"])
    ad.remote_status_raw={"status": "active", "title": "changed"}
    _sync_campaign_from_remote(ad)
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.RECONCILIATION
    assert campaign.name == "T"
