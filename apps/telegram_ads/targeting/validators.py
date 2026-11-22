"""Validation for Ad Creation Studio (draft vs submission)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from datetime import timedelta
from django.utils import timezone
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
        queries = [normalize_search_query(str(q)) for q in cfg.get("search_queries") or [] if str(q).strip()]
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
        from apps.telegram_ads.services.bot_eligibility import validate_bot_targets

        bot_errors = validate_bot_targets(
            bots,
            strict=strict,
            warnings=result.warnings,
        )
        result.errors.extend(bot_errors)

    if target_type in {"users","channels"}:
        from apps.telegram_ads.targeting.normalize import parse_bot_peer_input
        included={str(peer).casefold() for peer in cfg.get("channel_ids",[])}
        excluded={str(peer).casefold() for peer in cfg.get("exclude_channel_ids",[])}
        if included & excluded:
            result.errors.append("یک کانال نمی‌تواند هم‌زمان در فهرست هدف و مستثنی‌ها باشد.")
        if any(type(peer) is not int and not parse_bot_peer_input(peer)[0] for key in ("channel_ids","exclude_channel_ids") for peer in cfg.get(key,[])):
            result.errors.append("نام کاربری کانال معتبر نیست.")
        if set(cfg.get("topic_ids",[])) & set(cfg.get("exclude_topic_ids",[])):
            result.errors.append("موضوع هدف و مستثنی نباید مشترک باشد.")
    if target_type == "users":
        if cfg.get("intersect_topics") and len(cfg.get("topic_ids",[]))<2:
            result.warnings.append("ترکیب علایق با کمتر از دو موضوع، تفاوتی ایجاد نمی‌کند.")
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
        channels = cfg.get("channel_ids") or []
        topics = cfg.get("topic_ids") or []
        langs = cfg.get("language_codes") or []
        # استراتژی مؤثر برای API از داده استنباط می‌شود (UI همه فیلدها را نشان می‌دهد).
        if channels:
            mode = "specific"
        elif topics:
            mode = "topics"
        else:
            mode = "language"
        # قانون تلگرام: با کانال مشخص، فیلد زبان باید خالی باشد.
        if channels and langs:
            result.errors.append("اگر کانال مشخص انتخاب شده، فیلد زبان باید خالی باشد.")
        if channels and topics:
            result.errors.append("اگر کانال مشخص انتخاب شده، فیلد موضوع باید خالی باشد.")
        if mode == "specific":
            if strict and not channels:
                result.errors.append("حداقل یک کانال مشخص انتخاب کنید.")
        elif mode == "topics":
            if strict and not topics:
                result.errors.append("حداقل یک موضوع برای هدف‌گیری کانال لازم است.")
            if strict and len(langs) != 1:
                result.errors.append("برای هدف‌گیری موضوعی باید یک زبان کانال انتخاب شود.")
        elif strict and not langs:
            result.warnings.append("حداقل یک زبان کانال پیشنهاد می‌شود.")
        elif not strict and not langs and not topics and not channels:
            result.warnings.append("هنوز زبان، موضوع یا کانال مشخصی انتخاب نشده است.")

    return result


def validate_audience_step(*, target_type: str, placement: str, config: dict[str, Any], strict: bool = True) -> StudioValidationResult:
    """Validate only audience/placement; later steps own creative and terms."""
    result = StudioValidationResult()
    if not target_type:
        if strict:
            result.errors.append("نوع هدف‌گیری را انتخاب کنید.")
        return result
    result.errors.extend(validate_target_placement(target_type, placement))
    audience = _validate_target_config(target_type, config, strict=strict)
    result.errors.extend(audience.errors)
    result.warnings.extend(audience.warnings)
    result.infos.extend(audience.infos)
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
    from apps.telegram_ads.targeting.website import validate_website_fields
    result.errors.extend(validate_website_fields(promote_url,settings,strict=strict))
    if (settings.get("schedule") or {}).get("use_viewer_timezone") and target_type != "users":
        result.errors.append("منطقه زمانی بیننده فقط با هدف‌گیری کاربران سازگار است.")
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
    result = validate_studio_config(
        target_type=campaign.target_type or "",
        placement=placement,
        config=config,
        promote_url=campaign.destination,
        ad_text=creative.ad_text if creative else "",
        title=campaign.name or (creative.title if creative else ""),
        ad_settings=campaign.ad_settings or {},
        strict=True,
    )
    from apps.telegram_ads.services.media import media_receipt
    if creative and creative.media:
        if not media_receipt(campaign):
            result.errors.append("شناسه معتبر رسانه از تلگرام دریافت نشده است؛ قبل از پرداخت فایل را منتقل یا حذف کنید.")
    elif (campaign.ad_settings or {}).get("photo_id") or (campaign.ad_settings or {}).get("video_id"):
        result.errors.append("شناسه رسانه قدیمی قابل تأیید نیست؛ فایل جدید ثبت کنید.")
    from apps.telegram_ads.targeting.website import website_submission_errors
    from apps.telegram_ads.services.website_photo import website_photo_receipt
    result.errors.extend(website_submission_errors(campaign.destination,campaign.ad_settings or {}))
    if creative and creative.website_photo and not website_photo_receipt(campaign):
        result.errors.append("تصویر وب‌سایت پیش از پرداخت باید با تأیید دریافت شناسه به تلگرام منتقل شود.")
    if config.get("audience_ids") or config.get("exclude_audience_ids"):
        result.errors.append("مخاطبان اختصاصی نیازمند مسیردهی حساب مستقل تأییدشده هستند.")
    if not campaign.destination:
        result.errors.append("مقصد تبلیغ الزامی است.")
    if campaign.budget_irr <= 0:
        result.errors.append("بودجه معتبر الزامی است.")
    if campaign.daily_cap_irr < 0 or campaign.daily_cap_irr > campaign.budget_irr:
        result.errors.append("سقف روزانه نامعتبر است.")
    if campaign.cpm_bid is not None:
        try:
            cpm = Decimal(str(campaign.cpm_bid))
            if not cpm.is_finite() or not 0 < cpm <= Decimal("99999999.99") or cpm != cpm.quantize(Decimal("0.01")):
                result.errors.append("CPM نامعتبر است.")
        except (ValueError, InvalidOperation):
            result.errors.append("CPM نامعتبر است.")
    current = timezone.now()
    for value in (campaign.schedule_start, campaign.schedule_end):
        if value and not current < value <= current + timedelta(days=365):
            result.errors.append("زمان‌بندی باید در آینده و حداکثر تا ۳۶۵ روز بعد باشد.")
    if campaign.schedule_start and campaign.schedule_end and campaign.schedule_end <= campaign.schedule_start:
        result.errors.append("زمان توقف باید بعد از زمان فعال‌سازی باشد.")
    return result
