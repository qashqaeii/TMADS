import pytest
from decimal import Decimal

from apps.accounts.models import User
from apps.campaigns.metrics import (
    aggregate_portfolio_kpis,
    build_campaign_list_rows,
    lifetime_metrics_for_advertisement,
)
from apps.campaigns.models import Campaign, CampaignStatisticsSnapshot, TelegramAdvertisement


@pytest.mark.django_db
def test_lifetime_prefers_remote_raw_not_sum_snapshots():
    user = User.objects.create_user(username="m1", password="x")
    customer = user.customer_profile
    campaign = Campaign.objects.create(customer=customer, name="A", status=Campaign.Status.ACTIVE)
    ad = TelegramAdvertisement.objects.create(
        campaign=campaign,
        remote_ad_id="1",
        remote_status_raw={"views": 100, "clicks": 10, "actions": 2, "spent_budget": "1.5", "currency": "TON"},
    )
    from datetime import date

    CampaignStatisticsSnapshot.objects.create(
        advertisement=ad,
        snapshot_date=date(2026, 1, 1),
        impressions=50,
        clicks=5,
        actions=1,
    )
    CampaignStatisticsSnapshot.objects.create(
        advertisement=ad,
        snapshot_date=date(2026, 1, 2),
        impressions=50,
        clicks=5,
        actions=1,
    )
    m = lifetime_metrics_for_advertisement(ad)
    assert m.impressions == 100
    assert m.clicks == 10
    assert m.spent_ton == Decimal("1.5")


@pytest.mark.django_db
def test_weighted_ctr():
    user = User.objects.create_user(username="m2", password="x")
    customer = user.customer_profile
    c1 = Campaign.objects.create(customer=customer, name="big", status=Campaign.Status.ACTIVE)
    c2 = Campaign.objects.create(customer=customer, name="small", status=Campaign.Status.PAUSED)
    TelegramAdvertisement.objects.create(
        campaign=c1,
        remote_ad_id="10",
        remote_status_raw={"views": 1000, "clicks": 100},
    )
    TelegramAdvertisement.objects.create(
        campaign=c2,
        remote_ad_id="11",
        remote_status_raw={"views": 100, "clicks": 50},
    )
    rows = build_campaign_list_rows(Campaign.objects.filter(customer=customer))
    kpis = aggregate_portfolio_kpis(rows)
    assert kpis["total_impressions"] == 1100
    assert kpis["total_clicks"] == 150
    assert kpis["weighted_ctr"] == round(150 * 100 / 1100, 2)


@pytest.mark.django_db
def test_missing_lifetime_and_video_opens_are_not_impressions():
    from datetime import date
    user = User.objects.create_user(username="missing", password="x")
    campaign = Campaign.objects.create(customer=user.customer_profile, name="Missing")
    ad = TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id="12", remote_status_raw={"opens": 12})
    CampaignStatisticsSnapshot.objects.create(advertisement=ad, snapshot_date=date(2026, 1, 1), impressions=300)
    m = lifetime_metrics_for_advertisement(ad)
    assert not m.has_impressions
    assert m.impressions == 0
    assert not m.has_stats
    ad.remote_status_raw = {"views": 0, "clicks": 0, "opens": 9, "currency": "EUR", "spent_budget": "3"}
    m = lifetime_metrics_for_advertisement(ad)
    assert m.has_impressions and m.has_stats and m.impressions == 0
    assert m.spent_ton is None
    assert not m.has_ctr
