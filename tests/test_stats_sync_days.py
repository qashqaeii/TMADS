from datetime import datetime, timezone as dt_timezone

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.campaigns.models import Campaign, TelegramAdvertisement
from apps.telegram_ads.services.sync import stats_sync_days


@pytest.mark.django_db
def test_stats_sync_days_uses_earliest_telegram_created_date():
    user = User.objects.create_user(username="sd1", password="x")
    customer = user.customer_profile
    campaign = Campaign.objects.create(customer=customer, name="imported", status=Campaign.Status.PAUSED)
    ts = int(datetime(2025, 12, 22, 13, 43, tzinfo=dt_timezone.utc).timestamp())
    ad = TelegramAdvertisement.objects.create(
        campaign=campaign,
        remote_ad_id="99",
        remote_status_raw={"created_date": ts, "views": 100},
    )
    days = stats_sync_days(ad, campaign, default=30, cap=1000)
    assert days >= 300
