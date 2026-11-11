"""Build createAd payloads from Campaign records."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.campaigns.models import Campaign
from apps.finance.services import ton_allocation_for_budget
from apps.telegram_ads.constants import TMADS_TO_API_PLACEMENT
from apps.telegram_ads.targeting.builders import build_input_target
from apps.telegram_ads.targeting.compatibility import resolve_api_placement
from apps.telegram_ads.targeting.normalize import parse_promote_url
from apps.telegram_ads.targeting.validators import validate_submission_ready
from telead.inputs import InputAdSchedule, serialize


def _unix_minute(dt: datetime | None) -> int | None:
    if not dt:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    return int(dt.timestamp())


def build_schedule(ad_settings: dict[str, Any]) -> dict[str, Any] | InputAdSchedule | None:
    raw = ad_settings.get("schedule")
    if not raw:
        return None
    if isinstance(raw, dict) and raw.get("week_hours_mask"):
        schedule = InputAdSchedule(
            week_hours_mask=[int(x) for x in raw["week_hours_mask"]],
            timezone=raw.get("timezone"),
            use_viewer_timezone=bool(raw.get("use_viewer_timezone")),
        )
        schedule.validate()
        return schedule
    return None


def campaign_initial_budget_ton(campaign: Campaign) -> float:
    """Convert customer IRR budget to operator-account TON/Gram (approx)."""
    if campaign.budget_irr <= 0:
        return 0.0
    ton = ton_allocation_for_budget(campaign.budget_irr)
    return float(ton) if ton else 0.0


def campaign_daily_budget_limit_ton(campaign: Campaign) -> float:
    if campaign.daily_cap_irr <= 0:
        return 0.0
    ton = ton_allocation_for_budget(campaign.daily_cap_irr)
    return float(ton) if ton else 0.0


def build_create_ad_payload(
    campaign: Campaign,
    *,
    include_initial_budget: bool = True,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    validation = validate_submission_ready(campaign)
    if not validation.ok:
        raise ValueError("; ".join(validation.errors))

    creative = campaign.creatives.first()
    targeting = getattr(campaign, "targeting", None)
    config = targeting.config if targeting else {}
    target_type = campaign.target_type or "channels"
    target = build_input_target(target_type, config)

    placement = resolve_api_placement(campaign.placement or config.get("placement_api") or "", target_type)
    promote_url, url_errors = parse_promote_url(campaign.destination)
    if url_errors:
        raise ValueError(url_errors[0])

    settings = campaign.ad_settings or {}
    text = None if target_type == "search" else (creative.ad_text if creative else "")
    title = (campaign.name or (creative.title if creative else "") or "TMADS").strip()

    payload: dict[str, Any] = {
        "title": title,
        "promote_url": promote_url,
        "cpm": float(campaign.cpm_bid or Decimal("1")),
        "placement": placement,
        "target": serialize(target),
        "return_target": True,
        "idempotency_key": idempotency_key or f"tmads-create-{campaign.id}-{uuid.uuid4()}",
    }
    if text:
        payload["text"] = text.strip()

    freq = settings.get("impression_frequency")
    if freq:
        payload["impression_frequency"] = int(freq)

    if settings.get("show_userpic"):
        payload["show_userpic"] = True
    if settings.get("additional_info"):
        payload["additional_info"] = str(settings["additional_info"])[:64]
    if settings.get("website_name"):
        payload["website_name"] = settings["website_name"]
    if settings.get("website_photo_id"):
        payload["website_photo_id"] = settings["website_photo_id"]
    if settings.get("button"):
        payload["button"] = settings["button"]
    if settings.get("conversion_event_id"):
        payload["conversion_event_id"] = settings["conversion_event_id"]
    if settings.get("photo_id"):
        payload["photo_id"] = settings["photo_id"]
    if settings.get("video_id"):
        payload["video_id"] = settings["video_id"]

    schedule = build_schedule(settings)
    if schedule:
        payload["schedule"] = serialize(schedule) if hasattr(schedule, "to_dict") else schedule

    activate = _unix_minute(campaign.schedule_start)
    deactivate = _unix_minute(campaign.schedule_end)
    if activate:
        payload["activate_date"] = activate
    if deactivate:
        payload["deactivate_date"] = deactivate

    if settings.get("remote_initial_status") == "on_hold" or settings.get("is_paused"):
        payload["is_paused"] = True

    daily_ton = campaign_daily_budget_limit_ton(campaign)
    if daily_ton > 0:
        payload["daily_budget_limit"] = daily_ton

    if include_initial_budget:
        initial = campaign_initial_budget_ton(campaign)
        if initial > 0:
            payload["initial_budget"] = initial

    return payload


def redact_payload_for_display(payload: dict[str, Any]) -> dict[str, Any]:
    """Safe diagnostic view (no secrets)."""
    out = dict(payload)
    for key in ("account_id",):
        out.pop(key, None)
    return out
