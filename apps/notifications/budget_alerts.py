"""Reliable low-budget in-app alerts from confirmed lifetime TON balances.

Does not spend funds, change CPM, pause ads or send external notifications.
Alert deduplication is enforced in the database, not in worker memory.
"""
from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.utils import timezone

from apps.campaigns.models import Campaign, TelegramAdvertisement
from apps.notifications.models import Notification


def _balance(raw):
    if not isinstance(raw, dict) or raw.get("currency") != "TON":
        return None
    try:
        spent = Decimal(str(raw["spent_budget"]))
        remaining = Decimal(str(raw["remaining_budget"]))
        if not (spent.is_finite() and remaining.is_finite()
                and spent >= 0 and remaining >= 0 and spent + remaining > 0):
            return None
        return spent, remaining
    except (KeyError, InvalidOperation, ValueError, TypeError):
        return None


def assess_low_budget(ad, *, now=None):
    """Pure rule, returns alert metadata only on fresh, verified TON lifetime data."""
    now = now or timezone.now()
    if ad.campaign.status != Campaign.Status.ACTIVE:
        return None
    if not ad.updated_at or ad.updated_at > now + timedelta(minutes=2) or now - ad.updated_at > timedelta(hours=6):
        return None
    preferences = ad.campaign.ad_settings or {}
    selected = preferences.get("budget_alert_threshold", 20)
    if type(selected) is not int or selected not in (0, 5, 10, 20):
        selected = 20
    if selected == 0:
        return None
    raw = ad.remote_status_raw
    balance = _balance(raw)
    if balance is None:
        return None
    spent, remaining = balance
    percentage = remaining * Decimal("100") / (spent + remaining)
    if percentage <= 5:
        threshold, severity = 5, "warning"
    elif percentage <= selected:
        threshold, severity = selected, "info"
    else:
        return None
    return {
        "event_key": f"tmads:ad:{ad.pk}:budget:{threshold}",
        "title": "بودجه تبلیغ رو به پایان است" if threshold == 20 else "مانده بودجه تبلیغ بسیار کم است",
        "body": f"مانده بودجه تبلیغ «{ad.campaign.name or 'بدون نام'}» به حدود {percentage:.1f}٪ رسیده است. برای جزئیات وضعیت تلگرام را بررسی کنید.",
        "level": severity,
    }


def send_budget_alerts():
    """Safe to execute concurrently or repeatedly; no Telegram API calls."""
    created = 0
    ads = TelegramAdvertisement.objects.exclude(remote_ad_id="").select_related(
        "campaign__customer",
    ).filter(campaign__status=Campaign.Status.ACTIVE)
    for ad in ads.iterator(chunk_size=100):
        if ad.campaign.customer.is_suspended:
            continue
        alert = assess_low_budget(ad)
        if not alert:
            continue
        _, made = Notification.objects.get_or_create(
            customer=ad.campaign.customer, event_key=alert["event_key"],
            defaults={
                "title": alert["title"],
                "body": alert["body"],
                "level": alert["level"],
                "related_campaign_id": ad.campaign_id,
            },
        )
        created += int(made)
    return created
