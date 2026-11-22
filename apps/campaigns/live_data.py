"""Live Gram rate + campaign stats refresh for customer UI (no manual refresh required)."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import CustomerProfile
from apps.campaigns.models import Campaign, TelegramAdvertisement

logger = logging.getLogger(__name__)

LIVE_STATS_MAX_AGE_SECONDS = int(getattr(settings, "LIVE_STATS_MAX_AGE_SECONDS", 90))
LIVE_STATS_LOCK_SECONDS = 55
LIVE_STATS_FRESH_MARK_SECONDS = max(LIVE_STATS_MAX_AGE_SECONDS - 5, 30)


def _ads_queryset(customer: CustomerProfile, campaign: Campaign | None) -> QuerySet[TelegramAdvertisement]:
    qs = TelegramAdvertisement.objects.filter(campaign__customer=customer).exclude(remote_ad_id="")
    if campaign is not None:
        qs = qs.filter(campaign=campaign)
    return qs.select_related("campaign")


def ads_needing_live_refresh(
    customer: CustomerProfile,
    *,
    campaign: Campaign | None = None,
    max_age_seconds: int | None = None,
) -> list[TelegramAdvertisement]:
    max_age = LIVE_STATS_MAX_AGE_SECONDS if max_age_seconds is None else max_age_seconds
    cutoff = timezone.now() - timedelta(seconds=max_age)
    stale: list[TelegramAdvertisement] = []
    for ad in _ads_queryset(customer, campaign):
        if ad.updated_at is None or ad.updated_at < cutoff:
            stale.append(ad)
    return stale


def customer_has_linked_ads(customer: CustomerProfile, *, campaign: Campaign | None = None) -> bool:
    return _ads_queryset(customer, campaign).exists()


def refresh_customer_live_stats(
    customer: CustomerProfile,
    *,
    campaign: Campaign | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Sync linked Telegram ads + daily stats for the customer (or one campaign).

    Skips work when recently refreshed (unless force=True). Uses a short lock
    so concurrent page loads do not stampede the Ads API.
    """
    from apps.telegram_ads.services.sync import (
        stats_sync_days,
        sync_ad_statistics_for,
        sync_advertisement_detail,
    )

    scope = str(campaign.pk) if campaign is not None else "portfolio"
    fresh_key = f"live-stats-fresh:{customer.pk}:{scope}"
    lock_key = f"live-stats-lock:{customer.pk}:{scope}"

    if not force and cache.get(fresh_key):
        return {
            "needed": False,
            "skipped": True,
            "refreshed": 0,
            "failed": 0,
            "reason": "fresh",
        }

    ads = list(_ads_queryset(customer, campaign))
    if not ads:
        return {
            "needed": False,
            "skipped": True,
            "refreshed": 0,
            "failed": 0,
            "reason": "no_ads",
        }

    if not force:
        stale = ads_needing_live_refresh(customer, campaign=campaign)
        if not stale:
            cache.set(fresh_key, 1, timeout=LIVE_STATS_FRESH_MARK_SECONDS)
            return {
                "needed": False,
                "skipped": True,
                "refreshed": 0,
                "failed": 0,
                "reason": "already_current",
            }
        targets = stale
    else:
        targets = ads

    if not cache.add(lock_key, True, timeout=LIVE_STATS_LOCK_SECONDS):
        return {
            "needed": True,
            "skipped": True,
            "refreshed": 0,
            "failed": 0,
            "reason": "locked",
        }

    refreshed = 0
    failed = 0
    try:
        for ad in targets:
            try:
                sync_advertisement_detail(ad)
                sync_ad_statistics_for(ad, days=stats_sync_days(ad, ad.campaign))
                refreshed += 1
            except Exception:
                failed += 1
                logger.exception("live_stats_sync_failed ad=%s", getattr(ad, "remote_ad_id", ""))
    finally:
        cache.delete(lock_key)

    if refreshed or not failed:
        cache.set(fresh_key, 1, timeout=LIVE_STATS_FRESH_MARK_SECONDS)

    return {
        "needed": True,
        "skipped": False,
        "refreshed": refreshed,
        "failed": failed,
        "reason": "synced",
    }
