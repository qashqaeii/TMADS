from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Prefetch, QuerySet
from django.utils import timezone

from apps.campaigns.models import Campaign, CampaignStatisticsSnapshot, TelegramAdvertisement


@dataclass(frozen=True)
class AdLifetimeMetrics:
    impressions: int
    clicks: int
    actions: int
    spent_ton: Decimal | None
    remaining_ton: Decimal | None
    cpm: Decimal | None
    has_stats: bool
    stats_source: str  # remote_raw | snapshot | none
    stats_stale: bool
    last_updated: timezone.datetime | None


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def lifetime_metrics_for_advertisement(ad: TelegramAdvertisement | None) -> AdLifetimeMetrics:
    """Lifetime totals — never sum daily snapshots."""
    empty = AdLifetimeMetrics(0, 0, 0, None, None, None, False, "none", False, None)
    if not ad:
        return empty

    raw = ad.remote_status_raw if isinstance(ad.remote_status_raw, dict) else {}
    impressions = _int(raw.get("views") if "views" in raw else raw.get("impressions"))
    if not impressions:
        impressions = _int(raw.get("opens"))
    clicks = _int(raw.get("clicks"))
    actions = _int(raw.get("actions") if "actions" in raw else raw.get("joins"))
    spent = _decimal(raw.get("spent_budget") if "spent_budget" in raw else raw.get("spent"))
    remaining = _decimal(raw.get("remaining_budget") if "remaining_budget" in raw else raw.get("remaining"))
    cpm = _decimal(raw.get("cpm"))
    source = "none"

    if impressions is not None or clicks is not None or actions is not None:
        source = "remote_raw"
        impressions = impressions or 0
        clicks = clicks or 0
        actions = actions or 0
    else:
        latest = (
            CampaignStatisticsSnapshot.objects.filter(advertisement=ad)
            .order_by("-snapshot_date")
            .first()
        )
        if latest:
            source = "snapshot"
            impressions = int(latest.impressions)
            clicks = int(latest.clicks)
            actions = int(latest.actions)
            if spent is None and latest.spent_ton is not None:
                spent = latest.spent_ton
        else:
            return empty

    last_updated = ad.updated_at
    stats_stale = False
    if last_updated:
        age = timezone.now() - last_updated
        stats_stale = age.total_seconds() > 3600 * 6

    has_stats = source != "none" and (impressions > 0 or clicks > 0 or actions > 0 or (spent and spent > 0))

    return AdLifetimeMetrics(
        impressions=impressions or 0,
        clicks=clicks or 0,
        actions=actions or 0,
        spent_ton=spent,
        remaining_ton=remaining,
        cpm=cpm,
        has_stats=has_stats,
        stats_source=source,
        stats_stale=stats_stale,
        last_updated=last_updated,
    )


def lifetime_metrics_for_campaign(campaign: Campaign) -> AdLifetimeMetrics:
    ad = campaign.remote_ads.exclude(remote_ad_id="").order_by("-updated_at").first()
    metrics = lifetime_metrics_for_advertisement(ad)
    if metrics.cpm is None and campaign.cpm_bid is not None:
        return AdLifetimeMetrics(
            impressions=metrics.impressions,
            clicks=metrics.clicks,
            actions=metrics.actions,
            spent_ton=metrics.spent_ton,
            remaining_ton=metrics.remaining_ton,
            cpm=campaign.cpm_bid,
            has_stats=metrics.has_stats,
            stats_source=metrics.stats_source,
            stats_stale=metrics.stats_stale,
            last_updated=metrics.last_updated,
        )
    return metrics


def ctr_percent(impressions: int, clicks: int) -> float:
    if not impressions:
        return 0.0
    return round(clicks * 100.0 / impressions, 2)


def campaign_sparkline(campaign: Campaign, *, days: int = 7) -> list[int]:
    """آخرین N روز نمایش روزانه (snapshot) — برای mini chart لیست."""
    rows = list(
        CampaignStatisticsSnapshot.objects.filter(advertisement__campaign=campaign)
        .order_by("snapshot_date")
        .values_list("impressions", flat=True)
    )
    if days and len(rows) > days:
        rows = rows[-days:]
    return [int(x) for x in rows]


@dataclass
class CampaignListRow:
    campaign: Campaign
    metrics: AdLifetimeMetrics
    remote_ad_id: str
    ctr: float
    placement_label: str
    sparkline: list[int]
    sparkline_max: int


def build_campaign_list_rows(campaigns: QuerySet[Campaign]) -> list[CampaignListRow]:
    rows: list[CampaignListRow] = []
    for campaign in campaigns:
        m = lifetime_metrics_for_campaign(campaign)
        ad = campaign.remote_ads.exclude(remote_ad_id="").first()
        spark = campaign_sparkline(campaign, days=7)
        rows.append(
            CampaignListRow(
                campaign=campaign,
                metrics=m,
                remote_ad_id=ad.remote_ad_id if ad else "",
                ctr=ctr_percent(m.impressions, m.clicks),
                placement_label=campaign.get_placement_display() if campaign.placement else "—",
                sparkline=spark,
                sparkline_max=max(spark) if spark else 0,
            )
        )
    return rows


def aggregate_portfolio_kpis(rows: list[CampaignListRow]) -> dict[str, Any]:
    active_count = sum(1 for r in rows if r.campaign.status == Campaign.Status.ACTIVE)
    total_impressions = sum(r.metrics.impressions for r in rows)
    total_clicks = sum(r.metrics.clicks for r in rows)
    total_actions = sum(r.metrics.actions for r in rows)
    weighted_ctr = ctr_percent(total_impressions, total_clicks)

    spent_values = [r.metrics.spent_ton for r in rows if r.metrics.spent_ton is not None]
    total_spent_ton = sum(spent_values, start=Decimal("0")) if spent_values else None

    any_stale = any(r.metrics.stats_stale for r in rows if r.metrics.has_stats)

    return {
        "campaign_count": len(rows),
        "active_count": active_count,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "total_actions": total_actions,
        "weighted_ctr": weighted_ctr,
        "total_spent_ton": total_spent_ton,
        "any_stale": any_stale,
    }


def sort_campaign_rows(rows: list[CampaignListRow], sort_key: str) -> list[CampaignListRow]:
    reverse = sort_key.startswith("-")
    key = sort_key.lstrip("-")
    if key == "views":
        return sorted(rows, key=lambda r: r.metrics.impressions, reverse=reverse)
    if key == "clicks":
        return sorted(rows, key=lambda r: r.metrics.clicks, reverse=reverse)
    if key == "ctr":
        return sorted(rows, key=lambda r: r.ctr, reverse=reverse)
    if key == "spent":
        return sorted(
            rows,
            key=lambda r: (r.metrics.spent_ton or Decimal("0")),
            reverse=reverse,
        )
    if key == "name":
        return sorted(rows, key=lambda r: (r.campaign.name or "").lower(), reverse=reverse)
    if key == "status":
        return sorted(rows, key=lambda r: r.campaign.status, reverse=reverse)
    return sorted(rows, key=lambda r: r.campaign.created_at, reverse=True)


def optimize_campaign_list_queryset(qs: QuerySet[Campaign]) -> QuerySet[Campaign]:
    return qs.prefetch_related(
        Prefetch(
            "remote_ads",
            queryset=TelegramAdvertisement.objects.exclude(remote_ad_id="").order_by("-updated_at"),
        ),
        "creatives",
    )
