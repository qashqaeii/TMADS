"""Alerts use confirmed TON balances only and are idempotent."""
from decimal import Decimal
from datetime import timedelta

import pytest
from django.utils import timezone
from apps.campaigns.models import Campaign, TelegramAdvertisement
from apps.notifications.models import Notification
from apps.notifications.budget_alerts import assess_low_budget, send_budget_alerts


@pytest.mark.django_db
def test_budget_alerts_dedupe_across_worker_runs(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile, name="Test",
        status=Campaign.Status.ACTIVE,
    )
    ad = TelegramAdvertisement.objects.create(
        campaign=campaign, remote_ad_id="999", remote_status="active",
        remote_status_raw={
            "currency": "TON", "spent_budget": "9.6", "remaining_budget": "0.4",
        },
    )
    assert assess_low_budget(ad)["event_key"].endswith("budget:5")
    assert send_budget_alerts() == 1
    assert send_budget_alerts() == 0
    assert Notification.objects.filter(customer=campaign.customer).count() == 1
    campaign.status = Campaign.Status.PAUSED
    campaign.save(update_fields=["status"])
    assert send_budget_alerts() == 0


@pytest.mark.django_db
def test_no_alert_for_stale_or_non_ton_stats(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile, status=Campaign.Status.ACTIVE,
    )
    ad = TelegramAdvertisement.objects.create(
        campaign=campaign, remote_ad_id="991", remote_status="active",
        remote_status_raw={"currency": "XTR", "spent_budget": 9, "remaining_budget": 1},
    )
    assert assess_low_budget(ad) is None
    ad.remote_status_raw = {"currency": "TON", "spent_budget": "NaN", "remaining_budget": "1"}
    assert assess_low_budget(ad) is None
    ad.remote_status_raw = {"currency": "TON", "spent_budget": "9", "remaining_budget": "1"}
    ad.updated_at = timezone.now() - timedelta(days=1)
    assert assess_low_budget(ad) is None


@pytest.mark.django_db
def test_no_synthetic_alert_when_balance_missing(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile, status=Campaign.Status.ACTIVE,
    )
    ad = TelegramAdvertisement.objects.create(
        campaign=campaign, remote_ad_id="992", remote_status="active",
        remote_status_raw={"currency": "TON", "spent_budget": "99"},
    )
    assert send_budget_alerts() == 0
