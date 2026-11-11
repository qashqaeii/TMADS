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
    fake_items = [{"from_time": ts, "views": 10, "clicks": 2, "actions": 1, "spent_budget": "0.1"}]

    class FakeClient:
        def get_ad_statistics(self, *args, **kwargs):
            return {"items": fake_items}

    monkeypatch.setattr(
        "apps.telegram_ads.services.sync.TelegramAdsClient",
        lambda: FakeClient(),
    )

    n = sync_ad_statistics_for(ad, days=7)
    assert n == 1
    snap = CampaignStatisticsSnapshot.objects.get(advertisement=ad)
    assert snap.impressions == 10
    assert snap.raw.get("kind") == "period"
