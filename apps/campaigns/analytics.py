from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import jdatetime
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.campaigns.metrics import ctr_percent, lifetime_metrics_for_campaign
from apps.campaigns.models import Campaign, CampaignStatisticsSnapshot


def _fa_date_label(value: date) -> str:
    j = jdatetime.date.fromgregorian(date=value)
    text = j.strftime("%m/%d")
    return text.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _period_metrics_from_snapshot(row: dict[str, Any]) -> tuple[int, int, int, Decimal]:
    impressions = int(row.get("impressions") or 0)
    clicks = int(row.get("clicks") or 0)
    actions = int(row.get("actions") or 0)
    spent = row.get("spent_ton")
    if spent is None or spent == "":
        spent_val = Decimal("0")
    else:
        spent_val = Decimal(str(spent))

    raw = row.get("raw")
    if isinstance(raw, dict):
        if impressions <= 0:
            impressions = int(raw.get("views") or raw.get("impressions") or raw.get("opens") or 0)
        if clicks <= 0:
            clicks = int(raw.get("clicks") or 0)
        if actions <= 0:
            actions = int(raw.get("actions") or raw.get("joins") or 0)
        if spent_val <= 0:
            raw_spent = raw.get("spent_budget")
            if raw_spent is None:
                raw_spent = raw.get("spent")
            if raw_spent is not None and raw_spent != "":
                spent_val = Decimal(str(raw_spent))

    return impressions, clicks, actions, spent_val


def _rows_for_campaign(campaign: Campaign, *, limit: int | None = 45) -> list[dict[str, Any]]:
    qs = (
        CampaignStatisticsSnapshot.objects.filter(advertisement__campaign=campaign)
        .order_by("snapshot_date")
        .values("snapshot_date", "impressions", "clicks", "actions", "spent_ton", "raw")
    )

    by_date: dict[date, dict[str, Any]] = {}
    for row in qs:
        snapshot_date = row["snapshot_date"]
        impressions, clicks, actions, spent_val = _period_metrics_from_snapshot(row)
        bucket = by_date.setdefault(
            snapshot_date,
            {
                "snapshot_date": snapshot_date,
                "impressions": 0,
                "clicks": 0,
                "actions": 0,
                "spent_ton": Decimal("0"),
            },
        )
        bucket["impressions"] += impressions
        bucket["clicks"] += clicks
        bucket["actions"] += actions
        bucket["spent_ton"] += spent_val

    rows = sorted(by_date.values(), key=lambda item: item["snapshot_date"])
    if limit is not None and limit > 0 and len(rows) > limit:
        rows = rows[-limit:]
    return rows


def chart_has_signal(payload: dict[str, Any]) -> bool:
    if not payload.get("dates"):
        return False
    for key in ("impressions", "clicks", "actions", "spent"):
        series = payload.get(key) or []
        if any((float(v) if key == "spent" else int(v)) > 0 for v in series):
            return True
    return False


def aggregate_campaign_metrics(campaign: Campaign) -> dict:
    m = lifetime_metrics_for_campaign(campaign)
    impressions = m.impressions
    clicks = m.clicks
    actions = m.actions
    ctr = ctr_percent(impressions, clicks)
    conversion_rate = round(actions * 100.0 / clicks, 2) if clicks else 0.0
    cost_per_action = None
    if actions and m.spent_ton is not None and m.spent_ton > 0:
        cost_per_action = (m.spent_ton / Decimal(actions)).quantize(Decimal("0.0001"))
    return {
        "impressions": impressions,
        "clicks": clicks,
        "actions": actions,
        "ctr": ctr,
        "conversion_rate": conversion_rate,
        "spent_ton": m.spent_ton,
        "remaining_ton": m.remaining_ton,
        "cpm": m.cpm,
        "cost_per_action": cost_per_action,
        "has_stats": m.has_stats,
        "stats_stale": m.stats_stale,
        "stats_source": m.stats_source,
        "last_updated": m.last_updated,
    }


def campaign_chart_payload(campaign: Campaign, *, limit: int | None = 30) -> dict:
    """Daily period stats from snapshots (not lifetime totals)."""
    payload = _chart_from_rows(_rows_for_campaign(campaign, limit=limit))
    if payload.get("dates"):
        payload["day_count"] = len(payload["dates"])
        payload["from_date"] = payload["dates"][0]
        payload["to_date"] = payload["dates"][-1]
    else:
        payload["day_count"] = 0
    return payload


def _chart_from_rows(rows: list[dict[str, Any]]) -> dict:
    dates = [r["snapshot_date"].isoformat() for r in rows]
    labels = [_fa_date_label(r["snapshot_date"]) for r in rows]
    impressions = [int(r["impressions"]) for r in rows]
    clicks = [int(r["clicks"]) for r in rows]
    actions = [int(r["actions"]) for r in rows]
    spent = [float(r["spent_ton"] or 0) for r in rows]
    ctr = [ctr_percent(imp, clk) for imp, clk in zip(impressions, clicks, strict=False)]
    return {
        "dates": dates,
        "date_labels": labels,
        "impressions": impressions,
        "clicks": clicks,
        "actions": actions,
        "spent": spent,
        "ctr": ctr,
    }


def portfolio_timeseries(customer, *, days: int = 30) -> dict:
    """جمع آمار روزانه همهٔ کمپین‌های مشتری (بازهٔ روزانه API)."""
    end = timezone.localdate()
    start = end - timedelta(days=days)
    grouped = (
        CampaignStatisticsSnapshot.objects.filter(
            advertisement__campaign__customer=customer,
            snapshot_date__gte=start,
            snapshot_date__lte=end,
        )
        .values("snapshot_date")
        .annotate(
            impressions=Coalesce(Sum("impressions"), 0),
            clicks=Coalesce(Sum("clicks"), 0),
            actions=Coalesce(Sum("actions"), 0),
            spent=Coalesce(Sum("spent_ton"), Decimal("0")),
        )
        .order_by("snapshot_date")
    )
    rows = [
        {
            "snapshot_date": g["snapshot_date"],
            "impressions": g["impressions"],
            "clicks": g["clicks"],
            "actions": g["actions"],
            "spent_ton": g["spent"],
        }
        for g in grouped
    ]
    return _chart_from_rows(rows)


def funnel_from_metrics(metrics: dict) -> dict:
    return {
        "impressions": int(metrics.get("impressions") or 0),
        "clicks": int(metrics.get("clicks") or 0),
        "actions": int(metrics.get("actions") or 0),
    }


def budget_delivery_context(campaign: Campaign, metrics: dict) -> dict:
    ad = campaign.remote_ads.exclude(remote_ad_id="").order_by("-updated_at").first()
    raw = ad.remote_status_raw if ad and isinstance(ad.remote_status_raw, dict) else {}
    spent = metrics.get("spent_ton")
    remaining = metrics.get("remaining_ton")
    total_ton = None
    percent = None
    if spent is not None and remaining is not None and (spent + remaining) > 0:
        total_ton = spent + remaining
        percent = float((spent / total_ton) * 100)
    daily_limit = raw.get("daily_budget_limit") or raw.get("daily_budget")
    daily_spent = raw.get("daily_spent_budget")
    return {
        "spent_ton": spent,
        "remaining_ton": remaining,
        "total_ton": total_ton,
        "spent_percent": round(percent, 1) if percent is not None else None,
        "is_paused": bool(raw.get("is_paused")),
        "remote_status": ad.remote_status if ad else "",
        "daily_budget_limit": _decimal_or_none(daily_limit),
        "daily_spent_budget": _decimal_or_none(daily_spent),
        "activate_date": raw.get("activate_date"),
        "deactivate_date": raw.get("deactivate_date"),
        "has_remote": bool(ad and ad.remote_ad_id),
    }


def _decimal_or_none(value) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _join_scalars(items: list | tuple | set, *, sep: str = "، ") -> str:
    return sep.join(str(x) for x in items if x is not None and str(x).strip())


def _peer_chip_items(peers: object) -> list[dict[str, str]]:
    """Chip rows for bots/channels from API sync or wizard usernames."""
    if not peers:
        return []
    if not isinstance(peers, list):
        text = str(peers)
        return [{"title": text, "subtitle": "", "copy": text, "initial": text[:1].upper() or "T"}]
    items: list[dict[str, str]] = []
    for peer in peers:
        if isinstance(peer, dict):
            title = (peer.get("title") or "").strip()
            username = (peer.get("username") or peer.get("name") or "").strip()
            if username and not username.startswith("@"):
                username = f"@{username}"
            bot_id = peer.get("bot_id")
            display = title or username
            if not display and bot_id is not None:
                display = f"ربات #{bot_id}"
            if not display:
                continue
            copy = username or title or (f"#{bot_id}" if bot_id is not None else display)
            subtitle = username if title and username else ""
            initial = (username or title or "?").lstrip("@")[:1].upper() or "T"
            items.append(
                {"title": display, "subtitle": subtitle, "copy": copy, "initial": initial},
            )
        else:
            raw = str(peer).strip()
            if not raw:
                continue
            handle = raw if raw.startswith("@") else raw
            initial = handle.lstrip("@")[:1].upper() or "T"
            items.append({"title": handle, "subtitle": "", "copy": handle, "initial": initial})
    return items


def _scalar_chip_items(values: object) -> list[dict[str, str]]:
    if not isinstance(values, (list, tuple)):
        text = str(values or "").strip()
        return [{"title": text, "subtitle": "", "copy": text, "initial": text[:1].upper() or "T"}] if text else []
    items: list[dict[str, str]] = []
    for value in values:
        text = str(value).strip()
        if text:
            items.append(
                {"title": text, "subtitle": "", "copy": text, "initial": text.lstrip("@")[:1].upper() or "T"},
            )
    return items


def targeting_display_rows(targeting) -> list[dict[str, Any]]:
    if not targeting or not isinstance(targeting.config, dict):
        return []
    cfg = targeting.config
    rows: list[dict[str, Any]] = []
    seen_labels: set[str] = set()

    def add_text_row(label: str, value: str) -> None:
        text = (value or "").strip()
        if not text or label in seen_labels:
            return
        seen_labels.add(label)
        rows.append({"label": label, "kind": "text", "value": text})

    def add_chip_row(label: str, items: list[dict[str, str]]) -> None:
        if not items or label in seen_labels:
            return
        seen_labels.add(label)
        copy_all = "\n".join(item["copy"] for item in items if item.get("copy"))
        rows.append(
            {
                "label": label,
                "kind": "chips",
                "items": items,
                "copy_all": copy_all,
                "value": _join_scalars([item["title"] for item in items]),
                "count": len(items),
            }
        )

    def add_list_row(label: str, values: object) -> None:
        if values is None or values == "":
            return
        if isinstance(values, (list, tuple)):
            items = _scalar_chip_items(values)
            if items:
                add_chip_row(label, items)
            return
        add_text_row(label, str(values))

    api = cfg.get("api_target")
    if isinstance(api, dict):
        langs = api.get("languages") or api.get("language_codes")
        if langs:
            add_list_row("زبان‌ها", langs)
        countries = api.get("countries") or api.get("country_codes")
        if countries:
            add_list_row("کشورها", countries)
        topics = api.get("topics") or api.get("topic_ids")
        if topics:
            add_list_row("موضوعات", topics)
        channels = api.get("channels") or api.get("channel_usernames")
        if channels:
            if isinstance(channels, list):
                add_chip_row("کانال‌ها", _peer_chip_items(channels))
            else:
                add_text_row("کانال‌ها", str(channels))
        bots = api.get("bots")
        if bots:
            add_chip_row("ربات‌ها", _peer_chip_items(bots))
        queries = api.get("search_queries")
        if queries:
            add_list_row("عبارت‌های جستجو", queries)

    if cfg.get("bot_ids"):
        add_chip_row("ربات‌ها", _peer_chip_items(cfg["bot_ids"]))
    if cfg.get("search_queries"):
        add_list_row("عبارت‌های جستجو", cfg["search_queries"])
    if cfg.get("channel_ids"):
        add_chip_row("کانال‌ها", _peer_chip_items(cfg["channel_ids"]))
    if cfg.get("language_codes"):
        add_list_row("زبان کانال", cfg["language_codes"])
    if cfg.get("topic_ids"):
        add_list_row("شناسه موضوعات", cfg["topic_ids"])
    if cfg.get("country_codes"):
        add_list_row("کشورها", cfg["country_codes"])
    if cfg.get("placement_api"):
        add_text_row("جایگاه API", str(cfg["placement_api"]))
    if cfg.get("channel_mode"):
        add_text_row("استراتژی کانال", str(cfg["channel_mode"]))
    if cfg.get("languages"):
        add_text_row("زبان (قدیمی)", str(cfg["languages"]))
    if cfg.get("topics"):
        add_text_row("موضوعات (قدیمی)", str(cfg["topics"]))
    if cfg.get("countries"):
        add_list_row("کشورها (قدیمی)", cfg["countries"])
    if cfg.get("advanced"):
        add_text_row("پیشرفته", str(cfg["advanced"]))
    return rows


_LIFECYCLE: list[tuple[str, str, set[str], str]] = [
    ("پیش‌نویس", "draft", {Campaign.Status.DRAFT}, "file-pen-line"),
    (
        "پرداخت",
        "pay",
        {
            Campaign.Status.AWAITING_PAYMENT,
            Campaign.Status.PAYMENT_PENDING,
            Campaign.Status.PAID,
        },
        "wallet",
    ),
    (
        "بررسی",
        "review",
        {
            Campaign.Status.PENDING_REVIEW,
            Campaign.Status.READY_FOR_SUBMISSION,
            Campaign.Status.SUBMITTING,
            Campaign.Status.AWAITING_TELEGRAM,
        },
        "clipboard-check",
    ),
    (
        "انتشار",
        "live",
        {Campaign.Status.ACTIVE, Campaign.Status.PAUSED},
        "radio",
    ),
    (
        "پایان",
        "done",
        {
            Campaign.Status.COMPLETED,
            Campaign.Status.REJECTED,
            Campaign.Status.CANCELLED,
            Campaign.Status.FAILED,
            Campaign.Status.RECONCILIATION,
        },
        "flag",
    ),
]


def campaign_lifecycle(campaign: Campaign) -> list[dict[str, Any]]:
    status = campaign.status
    matched_idx = 0
    for idx, (_label, _key, statuses, _icon) in enumerate(_LIFECYCLE):
        if status in statuses:
            matched_idx = idx
            break
    steps = []
    for idx, (label, key, statuses, icon) in enumerate(_LIFECYCLE):
        state = "upcoming"
        if idx < matched_idx:
            state = "done"
        elif idx == matched_idx:
            state = "current"
        steps.append(
            {
                "label": label,
                "key": key,
                "icon": icon,
                "index": idx,
                "state": state,
                "is_terminal": key == "done",
            }
        )
    return steps
