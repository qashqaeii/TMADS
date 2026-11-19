from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any

from django.db.models import Prefetch, QuerySet, Sum
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
    stats_source: str  # remote_raw | none
    stats_stale: bool
    last_updated: timezone.datetime | None
    has_impressions: bool = False
    has_clicks: bool = False
    has_actions: bool = False
    currency: str | None = None
    action_type: str = ""

    @property
    def has_ctr(self) -> bool:
        return self.has_impressions and self.has_clicks and self.impressions > 0


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (ArithmeticError, TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    parsed = _decimal(value)
    if parsed is None or parsed > 9223372036854775807 or parsed != parsed.to_integral_value():
        return None
    return int(parsed)


def lifetime_metrics_for_advertisement(ad: TelegramAdvertisement | None) -> AdLifetimeMetrics:
    """Use only lifetime fields, never a daily snapshot or video-open count."""
    if not ad:
        return AdLifetimeMetrics(0, 0, 0, None, None, None, False, "none", False, None)

    raw = ad.remote_status_raw if isinstance(ad.remote_status_raw, dict) else {}
    impressions = _int(raw.get("views", raw.get("impressions")))
    clicks = _int(raw.get("clicks"))
    actions = _int(raw.get("actions", raw.get("joins")))
    currency = str(raw.get("currency") or "").upper() or None
    # The ledger and display contract is TON. Missing/other currencies must not
    # be silently interpreted or converted as TON.
    spent = _decimal(raw.get("spent_budget", raw.get("spent"))) if currency == "TON" else None
    remaining = _decimal(raw.get("remaining_budget", raw.get("remaining"))) if currency == "TON" else None
    cpm = _decimal(raw.get("cpm")) if currency == "TON" else None
    has_stats = any(value is not None for value in (impressions, clicks, actions))
    last_updated = ad.updated_at
    return AdLifetimeMetrics(
        impressions=impressions or 0,
        clicks=clicks or 0,
        actions=actions or 0,
        spent_ton=spent,
        remaining_ton=remaining,
        cpm=cpm,
        has_stats=has_stats,
        stats_source="remote_raw" if has_stats else "none",
        stats_stale=bool(last_updated and (timezone.now() - last_updated).total_seconds() > 21600),
        last_updated=last_updated,
        has_impressions=impressions is not None,
        has_clicks=clicks is not None,
        has_actions=actions is not None,
        currency=currency,
        action_type=str(raw.get("action_type") or ""),
    )


def latest_linked_ad(campaign: Campaign) -> TelegramAdvertisement | None:
    cached = getattr(campaign, "_linked_ads", None)
    if cached is not None:
        return cached[0] if cached else None
    return campaign.remote_ads.exclude(remote_ad_id="").order_by("-updated_at").first()


def lifetime_metrics_for_campaign(campaign: Campaign) -> AdLifetimeMetrics:
    ad = latest_linked_ad(campaign)
    metrics = lifetime_metrics_for_advertisement(ad)
    if ad is None and campaign.cpm_bid is not None:
        return replace(metrics, cpm=campaign.cpm_bid)
    return metrics


def ctr_percent(impressions: int, clicks: int) -> float:
    if not impressions:
        return 0.0
    return round(clicks * 100.0 / impressions, 2)


def campaign_sparkline(campaign: Campaign, *, days: int = 7) -> list[int]:
    """آخرین N روز نمایش روزانه (snapshot) — برای mini chart لیست."""
    rows = list(
        CampaignStatisticsSnapshot.objects.filter(advertisement__campaign=campaign)
        .values("snapshot_date")
        .annotate(total=Sum("impressions"))
        .order_by("snapshot_date")
        .values_list("total", flat=True)
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
        ad = latest_linked_ad(campaign)
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
    comparable = [r for r in rows if r.metrics.has_impressions and r.metrics.has_clicks]
    ctr_impressions = sum(r.metrics.impressions for r in comparable)
    weighted_ctr = ctr_percent(ctr_impressions, sum(r.metrics.clicks for r in comparable))

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
        "has_impressions": any(r.metrics.has_impressions for r in rows),
        "has_clicks": any(r.metrics.has_clicks for r in rows),
        "has_ctr": ctr_impressions > 0,
        "stats_count": sum(r.metrics.has_stats for r in rows),
        "linked_count": sum(bool(r.remote_ad_id) for r in rows),
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
            to_attr="_linked_ads",
        ),
        "creatives",
    )
