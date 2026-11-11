"""Validation for Ad Creation Studio (draft vs submission)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from telead.limits import (
    AD_TEXT_MAX,
    AD_TITLE_MAX_BYTES,
    IMPRESSION_FREQUENCY_RANGE,
    TARGET_LIMITS,
)

from apps.telegram_ads.targeting.builders import build_input_target
from apps.telegram_ads.targeting.compatibility import validate_target_placement
from apps.telegram_ads.targeting.normalize import dedupe_preserve_order, normalize_search_query, parse_promote_url


@dataclass
class StudioValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    infos: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _validate_target_config(target_type: str, config: dict[str, Any], *, strict: bool) -> StudioValidationResult:
    result = StudioValidationResult()
    cfg = config or {}

    try:
        target = build_input_target(target_type, cfg)
        if strict:
            target.validate()
        else:
            try:
                target.validate()
            except Exception:
                pass
    except Exception as exc:
        result.errors.append(str(exc))
        return result

    if target_type == "search":
        queries = dedupe_preserve_order(
            [normalize_search_query(str(q)) for q in cfg.get("search_queries") or [] if str(q).strip()]
        )
        if strict and not queries:
            result.errors.append("حداقل یک عبارت جستجو لازم است.")
        if len(queries) > TARGET_LIMITS["search_queries"]:
            result.errors.append("تعداد عبارت‌های جستجو از سقف مجاز بیشتر است.")
        dup = len(queries) != len({q.casefold() for q in queries})
        if dup:
            result.errors.append("عبارت‌های تکراری در جستجو مجاز نیست.")

    if target_type == "bots":
        bots = cfg.get("bot_ids") or []
        if strict and not bots:
            result.errors.append("حداقل یک ربات برای نمایش تبلیغ انتخاب کنید.")

    if target_type == "users":
        placement = cfg.get("placement_api") or cfg.get("placement") or ""
        if strict and not placement:
            result.warnings.append("جایگاه نمایش برای کاربران انتخاب نشده است.")
        countries = cfg.get("country_codes") or []
        locations = cfg.get("location_ids") or []
        if locations and len(countries) != 1:
            result.errors.append("برای انتخاب شهر باید دقیقاً یک کشور سازگار انتخاب شود.")
        if strict and not countries and not locations and not (cfg.get("topic_ids") or cfg.get("channel_ids")):
            result.warnings.append("هدف‌گیری کاربران ممکن است بیش از حد محدود باشد.")

    if target_type == "channels":
        mode = cfg.get("channel_mode") or cfg.get("mode") or "language"
        if mode == "specific":
            if strict and not (cfg.get("channel_ids") or []):
                result.errors.append("حداقل یک کانال مشخص انتخاب کنید.")
        elif mode == "topics":
            if strict and not (cfg.get("topic_ids") or []):
                result.errors.append("حداقل یک موضوع برای هدف‌گیری کانال لازم است.")
            langs = cfg.get("language_codes") or []
            if strict and len(langs) != 1:
                result.errors.append("برای هدف‌گیری موضوعی باید یک زبان کانال انتخاب شود.")
        elif strict and not (cfg.get("language_codes") or []):
            result.warnings.append("حداقل یک زبان کانال پیشنهاد می‌شود.")

    return result


def validate_studio_config(
    *,
    target_type: str,
    placement: str,
    config: dict[str, Any],
    promote_url: str = "",
    ad_text: str = "",
    title: str = "",
    ad_settings: dict[str, Any] | None = None,
    strict: bool = False,
) -> StudioValidationResult:
    result = StudioValidationResult()
    if not target_type:
        if strict:
            result.errors.append("نوع هدف‌گیری را انتخاب کنید.")
        return result

    result.errors.extend(validate_target_placement(target_type, placement))

    if promote_url:
        _, url_errors = parse_promote_url(promote_url)
        if strict:
            result.errors.extend(url_errors)

    if target_type != "search" and strict:
        text = (ad_text or "").strip()
        if len(text) < 1:
            result.errors.append("متن تبلیغ الزامی است.")
        elif len(text) > AD_TEXT_MAX:
            result.errors.append("متن تبلیغ بیش از حد مجاز است.")

    if title and len(title.encode("utf-8")) > AD_TITLE_MAX_BYTES:
        result.errors.append("عنوان داخلی تبلیغ بیش از حد مجاز است.")

    settings = ad_settings or {}
    freq = settings.get("impression_frequency")
    if freq is not None:
        low, high = IMPRESSION_FREQUENCY_RANGE
        if not isinstance(freq, int) or not low <= freq <= high:
            result.errors.append("تعداد نمایش روزانه به هر کاربر نامعتبر است.")

    if settings.get("photo_id") and settings.get("video_id"):
        result.errors.append("فقط یکی از عکس یا ویدیو قابل استفاده است.")

    if target_type in {"channels", "users"}:
        if settings.get("photo_id") or settings.get("video_id"):
            result.infos.append("رسانه برای این هدف در API پشتیبانی می‌شود.")
    elif settings.get("photo_id") or settings.get("video_id"):
        result.warnings.append("رسانه برای این نوع هدف ممکن است توسط API پذیرفته نشود.")

    target_result = _validate_target_config(target_type, config, strict=strict)
    result.errors.extend(target_result.errors)
    result.warnings.extend(target_result.warnings)
    result.infos.extend(target_result.infos)

    if strict and not settings.get("terms_accepted"):
        result.errors.append("پذیرش قوانین قبل از ثبت سفارش الزامی است.")

    return result


def validate_submission_ready(campaign) -> StudioValidationResult:
    creative = campaign.creatives.first()
    targeting = getattr(campaign, "targeting", None)
    config = targeting.config if targeting else {}
    placement = campaign.placement or config.get("placement_api") or ""
    return validate_studio_config(
        target_type=campaign.target_type or "",
        placement=placement,
        config=config,
        promote_url=campaign.destination,
        ad_text=creative.ad_text if creative else "",
        title=campaign.name or (creative.title if creative else ""),
        ad_settings=campaign.ad_settings or {},
        strict=True,
    )
