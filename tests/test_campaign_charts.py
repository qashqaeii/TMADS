from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.campaigns.analytics import (
    _period_metrics_from_snapshot,
    campaign_chart_payload,
    chart_has_signal,
    portfolio_timeseries,
)
from apps.campaigns.models import Campaign, CampaignStatisticsSnapshot, TelegramAdvertisement


@pytest.mark.django_db
def test_chart_payload_includes_spent_and_ctr():
    user = User.objects.create_user(username="ch1", password="x")
    customer = user.customer_profile
    campaign = Campaign.objects.create(customer=customer, name="A", status=Campaign.Status.ACTIVE)
    ad = TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id="99")
    CampaignStatisticsSnapshot.objects.create(
        advertisement=ad,
        snapshot_date=date(2026, 3, 1),
        impressions=1000,
        clicks=50,
        actions=5,
        spent_ton=Decimal("0.5"),
    )
    payload = campaign_chart_payload(campaign, limit=30)
    assert payload["impressions"] == [1000]
    assert payload["ctr"] == [5.0]
    assert payload["spent"] == [0.5]
    assert payload["date_labels"]
    assert payload["day_count"] == 1


@pytest.mark.django_db
def test_chart_payload_all_days_when_no_limit():
    user = User.objects.create_user(username="ch3", password="x")
    customer = user.customer_profile
    campaign = Campaign.objects.create(customer=customer, name="B", status=Campaign.Status.ACTIVE)
    ad = TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id="88")
    base = date(2026, 1, 1)
    for i in range(40):
        CampaignStatisticsSnapshot.objects.create(
            advertisement=ad,
            snapshot_date=base + timedelta(days=i),
            impressions=i,
            clicks=1,
            actions=0,
        )
    limited = campaign_chart_payload(campaign, limit=30)
    assert limited["day_count"] == 30
    full = campaign_chart_payload(campaign, limit=None)
    assert full["day_count"] == 40


def test_period_metrics_reads_opens_from_raw():
    row = {
        "impressions": 0,
        "clicks": 2,
        "actions": 1,
        "spent_ton": 0,
        "raw": {"kind": "period", "opens": 1200, "clicks": 2, "actions": 1},
    }
    imp, clk, act, _ = _period_metrics_from_snapshot(row)
    assert imp == 1200
    assert clk == 2


def test_chart_has_signal_false_when_all_zero():
    assert chart_has_signal({"dates": ["2026-01-01"], "impressions": [0], "clicks": [0]}) is False


@pytest.mark.django_db
def test_portfolio_timeseries_sums_customer_ads():
    user = User.objects.create_user(username="ch2", password="x")
    customer = user.customer_profile
    c1 = Campaign.objects.create(customer=customer, name="A", status=Campaign.Status.ACTIVE)
    c2 = Campaign.objects.create(customer=customer, name="B", status=Campaign.Status.ACTIVE)
    ad1 = TelegramAdvertisement.objects.create(campaign=c1, remote_ad_id="1")
    ad2 = TelegramAdvertisement.objects.create(campaign=c2, remote_ad_id="2")
    d = timezone.localdate() - timedelta(days=2)
    CampaignStatisticsSnapshot.objects.create(
        advertisement=ad1, snapshot_date=d, impressions=100, clicks=10, actions=1
    )
    CampaignStatisticsSnapshot.objects.create(
        advertisement=ad2, snapshot_date=d, impressions=200, clicks=20, actions=2
    )
    chart = portfolio_timeseries(customer, days=60)
    assert chart["impressions"] == [300]
    assert chart["clicks"] == [30]
