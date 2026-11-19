from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.utils import timezone

from apps.campaigns.models import Campaign, CampaignStatisticsSnapshot, CampaignTargeting, TelegramAdvertisement
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.constants import API_TO_TMADS_PLACEMENT, STATS_INTERVAL_DAY
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.models import APIRequestLog
from apps.telegram_ads.status_map import map_remote_status_to_campaign

logger = logging.getLogger(__name__)


def log_api_request(operation: str, success: bool, meta: dict | None = None) -> None:
    APIRequestLog.objects.create(
        operation=operation,
        success=success,
        meta=meta or {},
    )


def sync_remote_advertisements_readonly() -> int:
    """Update linked ads from getAdsList (lifetime fields on Ad object)."""
    client = TelegramAdsClient()
    try:
        items = client.list_advertisements()
        log_api_request("list_advertisements", True, {"count": len(items)})
    except TelegramAdsError:
        log_api_request("list_advertisements", False)
        raise

    by_remote = {}
    for item in items:
        rid = str(item.get("ad_id") or item.get("id") or "")
        if rid:
            by_remote[rid] = item
    updated = 0
    for ad in TelegramAdvertisement.objects.exclude(remote_ad_id=""):
        item = by_remote.get(ad.remote_ad_id)
        if not item:
            continue
        _apply_remote_ad_payload(ad, item)
        ad.save(
            update_fields=[
                "remote_status",
                "remote_status_raw",
                "placement",
                "promotion_url",
                "updated_at",
            ]
        )
        _sync_campaign_from_remote(ad)
        updated += 1
    return updated


def sync_advertisement_detail(ad: TelegramAdvertisement) -> None:
    """Fetch single Ad via getAdsById with return_target."""
    if not ad.remote_ad_id:
        return
    client = TelegramAdsClient()
    try:
        data = client.get_ad(ad.remote_ad_id, return_target=True)
        log_api_request("get_ad", True, {"ad_id": ad.remote_ad_id})
    except TelegramAdsError:
        log_api_request("get_ad", False, {"ad_id": ad.remote_ad_id})
        raise
    _apply_remote_ad_payload(ad, data)
    ad.save(
        update_fields=[
            "remote_status",
            "remote_status_raw",
            "placement",
            "promotion_url",
            "updated_at",
        ]
    )
    _sync_campaign_from_remote(ad, include_target=True)


def _apply_remote_ad_payload(ad: TelegramAdvertisement, item: dict) -> None:
    ad.remote_status = str(item.get("status") or "")
    ad.remote_status_raw = item
    ad.placement = str(item.get("placement") or item.get("placement_type") or ad.placement or "")
    promotion = item.get("promote_url") or item.get("promotion_url") or ""
    if promotion:
        ad.promotion_url = str(promotion)


def _sync_campaign_from_remote(ad: TelegramAdvertisement, *, include_target: bool = False) -> None:
    campaign = ad.campaign
    if not campaign:
        return
    item = ad.remote_status_raw if isinstance(ad.remote_status_raw, dict) else {}
    title = (item.get("title") or "").strip()
    if title:
        campaign.name = title
    destination = (item.get("promote_url") or item.get("promotion_url") or "").strip()
    if destination:
        campaign.destination = destination
    api_pl = item.get("placement")
    if api_pl:
        campaign.placement = API_TO_TMADS_PLACEMENT.get(str(api_pl), str(api_pl))
    cpm = item.get("cpm")
    if cpm is not None:
        try:
            campaign.cpm_bid = Decimal(str(cpm))
        except Exception:
            pass
    # Remote display status must not undo a local submission/reconciliation lock.
    from apps.finance.models import AdvertisingOrder
    pending = AdvertisingOrder.objects.filter(campaign_id=campaign.pk, status=AdvertisingOrder.Status.SUBMITTING).exists()
    if pending or campaign.status in {Campaign.Status.SUBMITTING, Campaign.Status.RECONCILIATION}:
        return
    campaign.status = map_remote_status_to_campaign(item)
    update_fields = ["name", "destination", "placement", "status", "cpm_bid", "updated_at"]
    campaign.save(update_fields=update_fields)

    if include_target:
        target = item.get("target")
        if isinstance(target, dict) and target:
            CampaignTargeting.objects.update_or_create(
                campaign=campaign,
                defaults={"config": {"api_target": target, "synced_at": timezone.now().isoformat()}},
            )
        creative = campaign.creatives.first()
        ad_text = (item.get("text") or "").strip()
        if ad_text:
            if not creative:
                from apps.campaigns.models import AdCreative

                creative = AdCreative(campaign=campaign)
            creative.ad_text = ad_text
            creative.title = creative.title or title[:200]
            creative.save()


def _date_from_unix_ts(value) -> date | None:
    if value is None or value == "":
        return None
    try:
        ts = int(value)
        dt = datetime.fromtimestamp(ts, tz=dt_timezone.utc)
        return timezone.localdate(dt)
    except (TypeError, ValueError, OSError):
        return None


def _remote_ad_start_date(raw: dict) -> date | None:
    for key in ("created_date", "activate_date", "date_created", "activate_time"):
        start = _date_from_unix_ts(raw.get(key))
        if start:
            return start
    return None


def _campaign_panel_start_date(campaign: Campaign) -> date | None:
    created = campaign.created_at
    if not created:
        return None
    if timezone.is_naive(created):
        created = timezone.make_aware(created, timezone.get_current_timezone())
    return timezone.localtime(created).date()


def stats_sync_days(
    ad: TelegramAdvertisement,
    campaign: Campaign,
    *,
    default: int = 30,
    cap: int = 1000,
) -> int:
    """Days window for getAdStats — از تاریخ واقعی آگهی در تلگرام (نه فقط ایجاد در پنل)."""
    raw = ad.remote_status_raw if isinstance(ad.remote_status_raw, dict) else {}
    candidates: list[date] = []
    remote_start = _remote_ad_start_date(raw)
    if remote_start:
        candidates.append(remote_start)
    panel_start = _campaign_panel_start_date(campaign)
    if panel_start:
        candidates.append(panel_start)
    if not candidates:
        return default
    start = min(candidates)
    days = (timezone.localdate() - start).days + 2
    return min(max(days, default), cap)


def sync_days_for_campaign(campaign: Campaign, *, default: int = 30, cap: int = 1000) -> int:
    """Back-compat when only campaign is known (uses panel created_at)."""
    panel_start = _campaign_panel_start_date(campaign)
    if not panel_start:
        return default
    days = (timezone.localdate() - panel_start).days + 2
    return min(max(days, default), cap)


def sync_ad_statistics_for(ad: TelegramAdvertisement, *, days: int | None = None) -> int:
    """
    Pull getAdStats with daily interval — each snapshot row is a **period**, not lifetime.

    Lifetime KPIs must come from ``remote_status_raw`` (Ad object) via metrics module.
    """
    if not ad.remote_ad_id:
        return 0
    campaign = ad.campaign
    if days is None:
        days = stats_sync_days(ad, campaign) if campaign else 30
    client = TelegramAdsClient()
    now = timezone.now()
    from_time = now - timedelta(days=days)
    try:
        stats = client.get_ad_statistics(
            ad.remote_ad_id,
            from_time=from_time,
            to_time=now,
            interval=STATS_INTERVAL_DAY,
        )
        log_api_request("get_ad_stats", True, {"ad_id": ad.remote_ad_id, "days": days})
    except TelegramAdsError:
        log_api_request("get_ad_stats", False, {"ad_id": ad.remote_ad_id})
        raise

    items = stats.get("items") if isinstance(stats, dict) else []
    if not isinstance(items, list):
        return 0

    written = 0
    for row in items:
        if not isinstance(row, dict):
            continue
        snapshot_date = _snapshot_date_from_stat(row)
        if not snapshot_date:
            continue
        impressions = int(row.get("views") or row.get("impressions") or row.get("opens") or 0)
        clicks = int(row.get("clicks") or 0)
        actions = int(row.get("actions") or row.get("joins") or 0)
        spent = row.get("spent_budget") or row.get("spent") or 0
        CampaignStatisticsSnapshot.objects.update_or_create(
            advertisement=ad,
            snapshot_date=snapshot_date,
            defaults={
                "impressions": impressions,
                "clicks": clicks,
                "actions": actions,
                "spent_ton": Decimal(str(spent)),
                "raw": {"kind": "period", "interval": STATS_INTERVAL_DAY, **row},
            },
        )
        written += 1
    return written


def _snapshot_date_from_stat(row: dict):
    ts = row.get("from_time")
    if ts is None:
        return None
    try:
        dt = datetime.fromtimestamp(int(ts), tz=dt_timezone.utc)
        return timezone.localdate(dt)
    except (TypeError, ValueError, OSError):
        return None
