"""Ad Creation Studio — ۵ مرحله، سازگار با ویزارد قدیمی ۸ مرحله‌ای."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import timezone

from apps.campaigns.models import AdCreative, Campaign, CampaignTargeting
from apps.campaigns.schedule_utils import parse_schedule_payload
from apps.core.dates import parse_local_datetime, to_western_digits
from apps.telegram_ads.constants import TMADS_TO_API_PLACEMENT
from apps.telegram_ads.targeting.compatibility import default_placement_for_target
from apps.telegram_ads.targeting.normalize import normalize_search_query, normalize_username, parse_promote_url
from apps.telegram_ads.targeting.validators import validate_audience_step, validate_studio_config

STUDIO_STEPS = [
    ("goal", "کجا نشون بدم"),
    ("audience", "کی ببینه"),
    ("creative", "متن تبلیغ"),
    ("budget", "بودجه و زمان"),
    ("review", "نگاه آخر"),
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


def studio_furthest_step(campaign: Campaign) -> int:
    """Highest step the advertiser has reached (for clickable stepper jumps)."""
    current = ensure_studio_step(campaign)
    raw = (campaign.wizard_data or {}).get("studio_furthest_step")
    try:
        stored = int(raw)
    except (TypeError, ValueError):
        stored = 0
    return max(1, min(max(stored, current), len(STUDIO_STEPS)))


def bump_studio_furthest_step(campaign: Campaign, reached: int | None = None) -> None:
    target = ensure_studio_step(campaign) if reached is None else int(reached)
    target = max(1, min(target, len(STUDIO_STEPS)))
    wd = dict(campaign.wizard_data or {})
    prev = studio_furthest_step(campaign)
    if target <= prev and int(wd.get("studio_furthest_step") or 0) >= prev:
        return
    wd["studio_furthest_step"] = max(prev, target)
    campaign.wizard_data = wd


def migrate_campaign_to_studio(campaign: Campaign) -> None:
    if campaign.wizard_version >= 2 and campaign.target_type:
        return
    wd = campaign.wizard_data or {}
    target = campaign.target_type or wd.get("target_type") or _infer_target_from_legacy(campaign)
    campaign.target_type = target
    campaign.wizard_step = ensure_studio_step(campaign)
    campaign.wizard_version = 2
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
        if len(bots) == 1 and "\n" in bots[0]:
            bots = [ln.strip() for ln in bots[0].splitlines() if ln.strip()]
        single = (data.get("bot_input") or "").strip()
        if single:
            bots.append(normalize_username(single))
        from apps.telegram_ads.targeting.normalize import parse_bot_peer_input
        from apps.telegram_ads.services.bot_eligibility import cached_bot_checks

        cfg["bot_ids"] = [parse_bot_peer_input(b)[0] or str(b).strip()[:256] for b in bots if b]
        cfg["bot_peer_checks"] = cached_bot_checks(cfg["bot_ids"])

    elif target_type == "channels":
        from apps.telegram_ads.targeting.normalize import parse_bot_peer_input

        def peers(key):
            values = [line.strip() for raw in getlist(key) for line in raw.splitlines() if line.strip()]
            return [parse_bot_peer_input(value)[0] or value for value in values]

        language_codes = getlist("language_codes") or getlist("channel_languages")
        topic_ids = [int(x) for x in getlist("topic_ids") if str(x).isdigit()]
        channel_ids = peers("channel_ids")
        # UI مثل تلگرام همه فیلدها را نشان می‌دهد؛ استراتژی API از داده استنباط می‌شود.
        if channel_ids:
            mode = "specific"
            # قانون تلگرام: با کانال مشخص، زبان/موضوع باید خالی بمانند.
            language_codes = []
            topic_ids = []
        elif topic_ids:
            mode = "topics"
        else:
            mode = "language"
        explicit = (data.get("channel_mode") or "").strip()
        if explicit in {"specific", "topics", "language"} and not channel_ids and not topic_ids and not language_codes:
            mode = explicit
        cfg["channel_mode"] = mode
        cfg["language_codes"] = language_codes
        cfg["topic_ids"] = topic_ids
        cfg["channel_ids"] = channel_ids
        cfg["exclude_topic_ids"] = [int(x) for x in getlist("exclude_topic_ids") if str(x).isdigit()]
        cfg["exclude_channel_ids"] = peers("exclude_channel_ids")

    elif target_type == "users":
        cfg["country_codes"] = [c.upper() for c in getlist("country_codes")]
        cfg["location_ids"] = [int(x) for x in getlist("location_ids") if str(x).isdigit()]
        cfg["language_codes"] = getlist("language_codes")
        cfg["topic_ids"] = [int(x) for x in getlist("topic_ids") if str(x).isdigit()]
        cfg["exclude_topic_ids"] = [int(x) for x in getlist("exclude_topic_ids") if str(x).isdigit()]
        cfg["intersect_topics"] = data.get("intersect_topics") == "1"
        from apps.telegram_ads.targeting.normalize import parse_bot_peer_input
        for field in ("channel_ids","exclude_channel_ids"):
            values=[line.strip() for raw in getlist(field) for line in raw.splitlines() if line.strip()]
            cfg[field]=[parse_bot_peer_input(value)[0] or value for value in values]
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

    mode = (data.get("studio_mode") or data.get("simple_mode") or "").strip()
    if mode in ("simple", "professional"):
        campaign.wizard_data = {**(campaign.wizard_data or {}), "studio_mode": mode}

    if step == 1:
        target_type = (data.get("target_type") or campaign.target_type or "").strip()
        if target_type and target_type != campaign.target_type:
            campaign.target_type = target_type
            campaign.placement = default_placement_for_target(target_type)
            CampaignTargeting.objects.filter(campaign=campaign).delete()
        promote, _ = parse_promote_url((data.get("destination") or campaign.destination or "").strip())
        if promote:
            campaign.destination = promote
        title = (data.get("campaign_name") or data.get("ad_title") or "").strip()
        if title:
            campaign.name = title
        settings = dict(campaign.ad_settings or {})
        settings["destination_rights_confirmed"] = data.get("destination_rights_confirmed") == "1"
        campaign.ad_settings = settings

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
            from apps.campaigns.media_validation import validate_telegram_creative_media

            errs = validate_telegram_creative_media(upload)
            if errs:
                raise ValueError("؛ ".join(errs))
            creative.media = upload
        elif data.get("remove_creative_media") == "1":
            # Do not delete a storage object which another cloned/legacy row might reference.
            creative.media = ""
        website_upload = (files or {}).get("website_photo") if files else None
        if website_upload:
            from apps.campaigns.media_validation import validate_website_photo
            errors = validate_website_photo(website_upload)
            if errors:
                raise ValueError("؛ ".join(errors))
            creative.website_photo = website_upload
        elif data.get("remove_website_photo") == "1":
            creative.website_photo = ""
        creative.save()
        promote, _ = parse_promote_url((data.get("destination") or campaign.destination or "").strip())
        if promote:
            campaign.destination = promote
        settings = dict(campaign.ad_settings or {})
        for key in ("show_userpic", "destination_rights_confirmed", "profile_complete_confirmed",
                    "channel_active_confirmed", "bot_functional_confirmed"):
            settings[key] = data.get(key) == "1"
        from apps.telegram_ads.targeting.website import website_fields
        for key in ("website_name","button","website_photo_id","conversion_event_id"):
            settings.pop(key,None)
        settings.update(website_fields(campaign.destination,data))
        campaign.ad_settings = settings

    elif step == 4:
        errors = validate_budget_inputs(campaign, data, strict=False)
        if errors:
            raise ValueError("؛ ".join(errors))
        direct = bool(
            campaign.telegram_connection_id
            and campaign.telegram_connection.connection_type == "customer_owned"
        )
        if direct:
            if "account_budget_amount" in data:
                campaign.account_budget_amount = parse_studio_decimal_amount(
                    data.get("account_budget_amount")
                ) or Decimal("0")
            if "account_daily_budget_limit" in data:
                campaign.account_daily_budget_limit = parse_studio_decimal_amount(
                    data.get("account_daily_budget_limit")
                ) or Decimal("0")
            campaign.budget_currency = campaign.telegram_connection.currency
            campaign.budget_irr = 0
            campaign.daily_cap_irr = 0
        else:
            if "budget_toman" in data:
                from apps.finance.services.money import toman_to_irr

                campaign.budget_irr = toman_to_irr(parse_studio_int_amount(data.get("budget_toman")))
            if "daily_cap_toman" in data:
                from apps.finance.services.money import toman_to_irr

                raw_daily = parse_studio_int_amount(data.get("daily_cap_toman"))
                campaign.daily_cap_irr = toman_to_irr(raw_daily) if raw_daily else 0
            campaign.account_budget_amount = 0
            campaign.account_daily_budget_limit = 0
            campaign.budget_currency = ""
        if "cpm_bid" in data:
            campaign.cpm_bid = parse_studio_decimal_amount(data.get("cpm_bid"))
        title = (data.get("campaign_name") or data.get("ad_title") or "").strip()
        if title:
            campaign.name = title[:128]
        settings = dict(campaign.ad_settings or {})
        parsed = parse_ad_settings(data)
        for key in ("impression_frequency", "remote_initial_status"):
            if key in parsed:
                settings[key] = parsed[key]
        if "additional_info" in parsed:
            settings["additional_info"] = parsed["additional_info"]
        elif "additional_info" in data and not str(data.get("additional_info") or "").strip():
            settings.pop("additional_info", None)
        if parsed.get("schedule"):
            settings["schedule"] = parsed["schedule"]
        elif not data.get("schedule_enabled"):
            settings.pop("schedule", None)
        campaign.ad_settings = settings
        for key in ("schedule_start", "schedule_end"):
            if key in data:
                value = parse_local_datetime(data[key])
                if value and timezone.is_naive(value):
                    value = timezone.make_aware(value)
                setattr(campaign, key, value)

    elif step == 5:
        settings = dict(campaign.ad_settings or {})
        settings["terms_accepted"] = data.get("terms_accepted") == "1"
        if settings["terms_accepted"]:
            settings["terms_accepted_at"] = timezone.now().isoformat()
        else:
            settings.pop("terms_accepted_at", None)
        campaign.ad_settings = settings

    campaign.save()


def parse_studio_int_amount(raw: Any) -> int:
    """Parse budget-like integers that may include Persian digits and thousand separators."""
    text = to_western_digits(raw or "").strip()
    if not text:
        return 0
    if re.search(r"[-−]", text):
        raise ValueError("negative integer amount")
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        raise ValueError("invalid integer amount")
    value = int(digits)
    if not 0 <= value <= 922337203685477:
        raise ValueError("integer amount out of range")
    return value


def parse_studio_decimal_amount(raw: Any) -> Decimal | None:
    """Parse CPM-like decimals with Persian/Arabic separators."""
    text = to_western_digits(raw or "").strip()
    if not text:
        return None
    if re.search(r"[-−]", text):
        raise ValueError("negative decimal amount")
    text = text.replace("٬", "").replace(",", "").replace("٫", ".")
    if not re.fullmatch(r"\d+(?:\.\d+)?", text):
        raise ValueError("invalid decimal amount")
    value = Decimal(text)
    if not value.is_finite():
        raise ValueError("invalid decimal amount")
    return value


def validate_budget_inputs(campaign, data, *, strict):
    errors = []
    direct = bool(
        campaign.telegram_connection_id
        and campaign.telegram_connection.connection_type == "customer_owned"
    )
    if direct:
        currency = campaign.telegram_connection.currency
        precision = {"TON": 2, "EUR": 2, "XTR": 0}.get(currency)
        if precision is None:
            return ["ارز حساب اختصاصی برای بودجه‌گذاری پشتیبانی نمی‌شود."]
        quantum = Decimal(1).scaleb(-precision)

        def direct_amount(key, previous):
            raw = data.get(key)
            if raw is None:
                return Decimal(str(previous or 0))
            try:
                value = parse_studio_decimal_amount(raw)
                if value is None:
                    value = Decimal("0")
                if not value.is_finite() or value < 0 or value > Decimal("999999999999"):
                    raise ValueError
                if value != value.quantize(quantum):
                    raise ValueError
                return value
            except (InvalidOperation, TypeError, ValueError):
                errors.append(f"مبالغ حساب {currency} باید با دقت مجاز همان ارز وارد شوند.")
                return Decimal(str(previous or 0))

        budget = direct_amount("account_budget_amount", campaign.account_budget_amount)
        daily = direct_amount("account_daily_budget_limit", campaign.account_daily_budget_limit)
        if strict and budget <= 0:
            errors.append("بودجه کمپین باید بیشتر از صفر باشد.")
        if strict and daily > budget:
            errors.append("سقف روزانه نباید بیشتر از بودجه کل باشد.")
        cpm_precision = precision
    else:
        def amount(key, previous):
            raw = data.get(key)
            if raw is None:
                return previous
            try:
                from apps.finance.services.money import toman_to_irr

                tomans = parse_studio_int_amount(raw)
                return toman_to_irr(tomans) if tomans else 0
            except (TypeError, ValueError):
                errors.append("بودجه و سقف روزانه باید عدد صحیح نامنفی باشند.")
                return previous
        budget = amount("budget_toman", campaign.budget_irr)
        daily = amount("daily_cap_toman", campaign.daily_cap_irr)
        if strict:
            from apps.core.dates import to_persian_digits
            from apps.finance.services.money import (
                irr_to_toman_int,
                minimum_advertising_budget_irr,
            )

            min_irr = minimum_advertising_budget_irr()
            if min_irr and budget < min_irr:
                min_toman = irr_to_toman_int(min_irr)
                min_fa = to_persian_digits(f"{min_toman:,}".replace(",", "٬"))
                errors.append(f"حداقل بودجه معادل ۱ گرام است (حدود {min_fa} تومان با نرخ روز).")
        if strict and daily > budget:
            errors.append("سقف روزانه نباید بیشتر از بودجه کل باشد.")
        cpm_precision = 2
    raw_cpm = data.get("cpm_bid")
    if raw_cpm not in (None, ""):
        try:
            cpm = parse_studio_decimal_amount(raw_cpm)
            quantum = Decimal(1).scaleb(-cpm_precision)
            if cpm is None or not 0 < cpm <= Decimal("99999999.99") or cpm != cpm.quantize(quantum):
                raise ValueError
        except (InvalidOperation, TypeError, ValueError):
            errors.append("هزینه هر هزار نمایش باید مثبت و با دقت مجاز ارز حساب باشد.")
    dates = []
    for key, previous in (("schedule_start", campaign.schedule_start), ("schedule_end", campaign.schedule_end)):
        raw = data.get(key)
        try:
            value = previous if raw is None else parse_local_datetime(raw)
            if value and timezone.is_naive(value):
                value = timezone.make_aware(value)
            dates.append(value)
            if strict and value and not timezone.now() < value <= timezone.now() + timedelta(days=365):
                errors.append("زمان‌بندی باید در آینده و حداکثر تا ۳۶۵ روز بعد باشد.")
        except (ValueError, TypeError, OverflowError):
            dates.append(None)
            errors.append("فرمت تاریخ زمان‌بندی معتبر نیست.")
    if strict and all(dates) and dates[1] <= dates[0]:
        errors.append("زمان توقف باید بعد از زمان فعال‌سازی باشد.")
    if data.get("schedule_enabled"):
        schedule=parse_schedule_payload(data)
        if strict and not schedule:
            errors.append("برای زمان‌بندی هفتگی حداقل یک بازه و منطقه زمانی معتبر انتخاب کنید.")
        if schedule and schedule.get("use_viewer_timezone") and campaign.target_type != "users":
            errors.append("زمان مخاطب فقط برای هدف‌گیری کاربران مجاز است.")
    return list(dict.fromkeys(errors))


def validate_studio_step(campaign: Campaign, step: int, data, *, strict: bool) -> list[str]:
    migrate_campaign_to_studio(campaign)
    if step == 1:
        target_type = data.get("target_type") or campaign.target_type
        if target_type not in Campaign.TargetType.values:
            return ["نوع هدف‌گیری معتبر را انتخاب کنید."]
        dest = (data.get("destination") or campaign.destination or "").strip()
        if strict:
            _, errs = parse_promote_url(dest)
            if errs:
                return errs
        return []
    if step == 2:
        cfg = parse_targeting_payload(data, campaign.target_type or "channels")
        placement = (data.get("placement") or campaign.placement or cfg.get("placement_api") or "")
        result = validate_audience_step(
            target_type=campaign.target_type or cfg.get("target_type", ""),
            placement=placement,
            config=cfg,
            strict=strict,
        )
        return result.errors
    if step == 3:
        from apps.telegram_ads.targeting.website import validate_website_fields, website_fields
        destination=(data.get("destination") or campaign.destination or "").strip()
        normalized,url_errors=parse_promote_url(destination)
        errors=validate_website_fields(normalized,website_fields(normalized,data),strict=strict)
        if strict:
            errors.extend(url_errors)
        if campaign.target_type != Campaign.TargetType.SEARCH:
            text = (data.get("ad_text") or "").strip()
            if strict and len(text) < 1:
                errors.append("متن تبلیغ را وارد کنید.")
            if len(text) > 160:
                errors.append("متن تبلیغ بیش از حد مجاز است.")
        return errors
    if step == 4:
        return validate_budget_inputs(campaign, data, strict=strict)
    if step == 5 and strict:
        # Review validation must not rewrite budget, dates or schedule.
        result = validate_studio_config(
            target_type=campaign.target_type,
            placement=campaign.placement,
            config=getattr(getattr(campaign, "targeting", None), "config", {}) or {},
            promote_url=campaign.destination,
            ad_text=(campaign.creatives.first().ad_text if campaign.creatives.first() else ""),
            title=campaign.name,
            ad_settings={**(campaign.ad_settings or {}), "terms_accepted": data.get("terms_accepted") == "1"},
            strict=True,
        )
        return result.errors
    return []


def studio_payload_from_post(data) -> dict[str, Any]:
    """Flat dict for wizard_data / autosave."""
    out: dict[str, Any] = {}
    for key in data.keys():
        if key in {
            "csrfmiddlewaretoken",
            "action",
            "draft_revision",
            "studio_step",
            "goto_step",
            "quote_nonce",
            "bot_eligibility_json",
        }:
            continue
        if hasattr(data, "getlist"):
            values = data.getlist(key)
            out[key] = values if len(values) > 1 else (values[0] if values else "")
        else:
            out[key] = data.get(key)
    return out
