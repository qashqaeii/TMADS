"""Ad Creation Studio — ۵ مرحله، سازگار با ویزارد قدیمی ۸ مرحله‌ای."""

from __future__ import annotations

import json
from typing import Any

from django.utils import timezone

from apps.campaigns.models import AdCreative, Campaign, CampaignTargeting
from apps.telegram_ads.constants import TMADS_TO_API_PLACEMENT
from apps.telegram_ads.targeting.compatibility import default_placement_for_target
from apps.telegram_ads.targeting.normalize import normalize_search_query, normalize_username, parse_promote_url
from apps.campaigns.schedule_utils import parse_schedule_payload
from apps.telegram_ads.targeting.validators import validate_studio_config

STUDIO_STEPS = [
    ("goal", "هدف تبلیغ"),
    ("audience", "مخاطبان و جایگاه"),
    ("creative", "محتوای تبلیغ"),
    ("budget", "بودجه و زمان‌بندی"),
    ("review", "بررسی و ثبت"),
]

LEGACY_STEP_COUNT = 8

# نگاشت مرحلهٔ قدیمی → استودیو (برای کمپین‌های import/قدیمی)
LEGACY_TO_STUDIO = {1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 5, 8: 5}

PLACEMENT_ALIASES = {
    **TMADS_TO_API_PLACEMENT,
    "channels": "channel_post",
    "video": "video_banner",
}


def ensure_studio_step(campaign: Campaign) -> int:
    step = campaign.wizard_step
    if campaign.wizard_version >= 2:
        return max(1, min(step, len(STUDIO_STEPS)))
    return LEGACY_TO_STUDIO.get(step, 1)


def migrate_campaign_to_studio(campaign: Campaign) -> None:
    if campaign.wizard_version >= 2 and campaign.target_type:
        return
    wd = campaign.wizard_data or {}
    target = campaign.target_type or wd.get("target_type") or _infer_target_from_legacy(campaign)
    campaign.target_type = target
    campaign.wizard_version = 2
    campaign.wizard_step = ensure_studio_step(campaign)
    if not campaign.placement:
        campaign.placement = default_placement_for_target(target)
    elif campaign.placement in PLACEMENT_ALIASES:
        campaign.placement = PLACEMENT_ALIASES[campaign.placement]
    campaign.save(
        update_fields=["target_type", "wizard_version", "wizard_step", "placement", "updated_at"]
    )


def _infer_target_from_legacy(campaign: Campaign) -> str:
    placement = campaign.placement or ""
    if placement in {"search_result", "search"}:
        return Campaign.TargetType.SEARCH
    if placement == "bot_banner" or campaign.objective == "bot":
        return Campaign.TargetType.BOTS
    if placement in {"video", "video_banner"}:
        return Campaign.TargetType.USERS
    if campaign.objective == "channel":
        return Campaign.TargetType.CHANNELS
    return Campaign.TargetType.CHANNELS


def parse_targeting_payload(data, target_type: str) -> dict[str, Any]:
    """Build canonical targeting config from POST."""

    def getlist(key: str) -> list[str]:
        if hasattr(data, "getlist"):
            return [str(x).strip() for x in data.getlist(key) if str(x).strip()]
        raw = data.get(key)
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]
        return [p.strip() for p in str(raw).split(",") if p.strip()]

    cfg: dict[str, Any] = {"target_type": target_type}

    if target_type == "search":
        raw_queries = data.get("search_queries_json") or data.get("search_queries") or ""
        if isinstance(raw_queries, str) and raw_queries.strip().startswith("["):
            try:
                queries = json.loads(raw_queries)
            except json.JSONDecodeError:
                queries = []
        elif hasattr(data, "getlist"):
            queries = data.getlist("search_queries")
        else:
            queries = [p.strip() for p in str(raw_queries).split("\n") if p.strip()]
        cfg["search_queries"] = [normalize_search_query(str(q)) for q in queries if str(q).strip()]

    elif target_type == "bots":
        bots = getlist("bot_ids")
        raw_area = data.get("bot_ids")
        if raw_area and not bots:
            bots = [ln.strip() for ln in str(raw_area).splitlines() if ln.strip()]
        single = (data.get("bot_input") or "").strip()
        if single:
            bots.append(normalize_username(single))
        cfg["bot_ids"] = [normalize_username(b) for b in bots if b]

    elif target_type == "channels":
        cfg["channel_mode"] = (data.get("channel_mode") or "language").strip()
        cfg["language_codes"] = getlist("language_codes") or getlist("channel_languages")
        cfg["topic_ids"] = [int(x) for x in getlist("topic_ids") if str(x).isdigit()]
        cfg["exclude_topic_ids"] = [int(x) for x in getlist("exclude_topic_ids") if str(x).isdigit()]
        channels = getlist("channel_ids")
        raw_ch = data.get("channel_ids")
        if raw_ch and not channels:
            channels = [ln.strip() for ln in str(raw_ch).splitlines() if ln.strip()]
        if data.get("channel_input"):
            channels.append(normalize_username(str(data.get("channel_input"))))
        cfg["channel_ids"] = [normalize_username(c) for c in channels if c]
        excl = getlist("exclude_channel_ids")
        if data.get("exclude_channel_input"):
            excl.append(normalize_username(str(data.get("exclude_channel_input"))))
        cfg["exclude_channel_ids"] = [normalize_username(c) for c in excl if c]

    elif target_type == "users":
        cfg["country_codes"] = [c.upper() for c in getlist("country_codes")]
        cfg["location_ids"] = [int(x) for x in getlist("location_ids") if str(x).isdigit()]
        cfg["language_codes"] = getlist("language_codes")
        cfg["topic_ids"] = [int(x) for x in getlist("topic_ids") if str(x).isdigit()]
        cfg["exclude_topic_ids"] = [int(x) for x in getlist("exclude_topic_ids") if str(x).isdigit()]
        cfg["intersect_topics"] = bool(data.get("intersect_topics"))
        cfg["device"] = (data.get("device") or "").strip() or None
        cfg["exclude_political_channels"] = bool(data.get("exclude_political_channels"))
        cfg["political_channels_only"] = bool(data.get("political_channels_only"))
        cfg["placement_api"] = (data.get("placement") or data.get("placement_api") or "").strip()

    return cfg


def parse_ad_settings(data) -> dict[str, Any]:
    settings = {}
    freq = (data.get("impression_frequency") or "").strip()
    if freq.isdigit():
        settings["impression_frequency"] = int(freq)
    if data.get("show_userpic"):
        settings["show_userpic"] = True
    if data.get("additional_info"):
        settings["additional_info"] = str(data.get("additional_info"))[:64]
    if data.get("remote_initial_status"):
        settings["remote_initial_status"] = data.get("remote_initial_status")
    if data.get("is_paused"):
        settings["is_paused"] = True
    if data.get("terms_accepted"):
        settings["terms_accepted"] = True
        settings["terms_accepted_at"] = timezone.now().isoformat()
    for key in (
        "destination_rights_confirmed",
        "channel_active_confirmed",
        "profile_complete_confirmed",
        "bot_has_photo",
        "bot_has_description",
        "bot_functional_confirmed",
    ):
        if data.get(key):
            settings[key] = True
    sched = parse_schedule_payload(data)
    if sched:
        settings["schedule"] = sched
    return settings


def apply_studio_step(campaign: Campaign, step: int, data, files=None) -> None:
    migrate_campaign_to_studio(campaign)

    if step == 1:
        target_type = (data.get("target_type") or campaign.target_type or "").strip()
        if target_type:
            campaign.target_type = target_type
        mode = (data.get("studio_mode") or data.get("simple_mode") or "").strip()
        if mode in ("simple", "professional"):
            campaign.wizard_data = {**(campaign.wizard_data or {}), "studio_mode": mode}
        promote, _ = parse_promote_url((data.get("destination") or campaign.destination or "").strip())
        if promote:
            campaign.destination = promote
        title = (data.get("campaign_name") or data.get("ad_title") or "").strip()
        if title:
            campaign.name = title

    elif step == 2:
        target_type = campaign.target_type or Campaign.TargetType.CHANNELS
        cfg = parse_targeting_payload(data, target_type)
        CampaignTargeting.objects.update_or_create(campaign=campaign, defaults={"config": cfg})
        placement = (data.get("placement") or cfg.get("placement_api") or "").strip()
        if placement:
            campaign.placement = PLACEMENT_ALIASES.get(placement, placement)

    elif step == 3:
        creative, _ = AdCreative.objects.get_or_create(campaign=campaign)
        if campaign.target_type != Campaign.TargetType.SEARCH:
            creative.ad_text = (data.get("ad_text") or "").strip()
        creative.title = (data.get("creative_title") or campaign.name or "").strip()
        creative.cta_label = (data.get("cta_label") or "").strip()
        upload = (files or {}).get("creative_media") if files else None
        if upload:
            from apps.campaigns.media_validation import validate_ad_image, validate_ad_video

            ctype = (getattr(upload, "content_type", "") or "").lower()
            errs = (
                validate_ad_image(upload)
                if ctype.startswith("image") or not ctype.startswith("video")
                else validate_ad_video(upload)
            )
            if not errs:
                creative.media = upload
        creative.save()
        promote, _ = parse_promote_url((data.get("destination") or campaign.destination or "").strip())
        if promote:
            campaign.destination = promote
        campaign.ad_settings = {**(campaign.ad_settings or {}), **parse_ad_settings(data)}

    elif step == 4:
        try:
            budget_toman = int(data.get("budget_toman") or 0)
        except (TypeError, ValueError):
            budget_toman = 0
        if budget_toman:
            campaign.budget_irr = budget_toman * 10_000
        try:
            daily_toman = int(data.get("daily_cap_toman") or 0)
        except (TypeError, ValueError):
            daily_toman = 0
        campaign.daily_cap_irr = daily_toman * 10_000 if daily_toman else 0
        cpm_raw = (data.get("cpm_bid") or "").strip()
        if cpm_raw:
            from decimal import Decimal, InvalidOperation

            try:
                campaign.cpm_bid = Decimal(cpm_raw)
            except InvalidOperation:
                pass
        settings = {**(campaign.ad_settings or {}), **parse_ad_settings(data)}
        if not data.get("schedule_enabled"):
            settings.pop("schedule", None)
        campaign.ad_settings = settings
        start_raw = (data.get("schedule_start") or "").strip()
        end_raw = (data.get("schedule_end") or "").strip()
        from django.utils import timezone as dj_tz

        if start_raw:
            campaign.schedule_start = dj_tz.datetime.fromisoformat(start_raw)
            if dj_tz.is_naive(campaign.schedule_start):
                campaign.schedule_start = dj_tz.make_aware(
                    campaign.schedule_start, dj_tz.get_current_timezone()
                )
        if end_raw:
            campaign.schedule_end = dj_tz.datetime.fromisoformat(end_raw)
            if dj_tz.is_naive(campaign.schedule_end):
                campaign.schedule_end = dj_tz.make_aware(
                    campaign.schedule_end, dj_tz.get_current_timezone()
                )

    elif step == 5:
        settings = {**(campaign.ad_settings or {}), **parse_ad_settings(data)}
        campaign.ad_settings = settings

    campaign.save()


def validate_studio_step(campaign: Campaign, step: int, data, *, strict: bool) -> list[str]:
    migrate_campaign_to_studio(campaign)
    if step == 1:
        if strict and not (data.get("target_type") or campaign.target_type):
            return ["نوع هدف‌گیری را انتخاب کنید."]
        dest = (data.get("destination") or campaign.destination or "").strip()
        if strict:
            _, errs = parse_promote_url(dest)
            if errs:
                return errs
        return []
    if step == 2:
        targeting = getattr(campaign, "targeting", None)
        cfg = parse_targeting_payload(data, campaign.target_type or "channels")
        placement = (data.get("placement") or campaign.placement or cfg.get("placement_api") or "")
        result = validate_studio_config(
            target_type=campaign.target_type or cfg.get("target_type", ""),
            placement=placement,
            config=cfg,
            strict=strict,
        )
        return result.errors
    if step == 3:
        if campaign.target_type == Campaign.TargetType.SEARCH:
            return []
        text = (data.get("ad_text") or "").strip()
        if strict and len(text) < 1:
            return ["متن تبلیغ را وارد کنید."]
        if len(text) > 160:
            return ["متن تبلیغ بیش از حد مجاز است."]
        return []
    if step == 4:
        try:
            budget = int(data.get("budget_toman") or 0)
        except (TypeError, ValueError):
            budget = 0
        if strict and budget < 100:
            return ["حداقل بودجه ۱۰۰ هزار تومان پیشنهاد می‌شود."]
        return []
    if step == 5 and strict:
        apply_studio_step(campaign, 4, data)
        result = validate_studio_config(
            target_type=campaign.target_type,
            placement=campaign.placement,
            config=getattr(getattr(campaign, "targeting", None), "config", {}) or {},
            promote_url=campaign.destination,
            ad_text=(campaign.creatives.first().ad_text if campaign.creatives.first() else ""),
            title=campaign.name,
            ad_settings={**(campaign.ad_settings or {}), **parse_ad_settings(data)},
            strict=True,
        )
        return result.errors
    return []


def studio_payload_from_post(data) -> dict[str, Any]:
    """Flat dict for wizard_data / autosave."""
    out: dict[str, Any] = {}
    for key in data.keys():
        if key in {"csrfmiddlewaretoken", "action"}:
            continue
        if hasattr(data, "getlist"):
            values = data.getlist(key)
            out[key] = values if len(values) > 1 else (values[0] if values else "")
        else:
            out[key] = data.get(key)
    return out
