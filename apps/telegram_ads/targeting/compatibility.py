"""Verified target type ↔ placement compatibility (conservative)."""

from __future__ import annotations

from typing import Any

from apps.telegram_ads.constants import API_PLACEMENTS, TMADS_TO_API_PLACEMENT

# API target.type values
TARGET_TYPES = frozenset({"search", "bots", "users", "channels"})

TARGET_TYPE_LABELS_FA = {
    "search": "تبلیغات جستجوی تلگرام",
    "bots": "تبلیغات در ربات‌ها",
    "users": "هدف‌گیری کاربران",
    "channels": "هدف‌گیری کانال‌ها",
}

# Documented + UI-verified combinations. Mark unverified pairs in matrix doc.
VERIFIED_TARGET_PLACEMENTS: dict[str, frozenset[str]] = {
    "search": frozenset({"search_result"}),
    "bots": frozenset({"bot_banner"}),
    "users": frozenset({"channel_post", "bot_banner", "video_banner"}),
    "channels": frozenset({"channel_post"}),
}

UNVERIFIED_TARGET_PLACEMENTS: dict[str, frozenset[str]] = {
    "search": frozenset(),
    "bots": frozenset(),
    "users": frozenset(),
    "channels": frozenset(),
}


def default_placement_for_target(target_type: str) -> str:
    verified = VERIFIED_TARGET_PLACEMENTS.get(target_type) or frozenset()
    if not verified:
        return "search_result"
    return sorted(verified)[0]


def placement_choices_for_target(target_type: str) -> list[dict[str, Any]]:
    """Choices for UI: api placement + Persian label + verification flag."""
    labels = {
        "search_result": ("نتایج جستجو", "جستجوی تلگرام"),
        "bot_banner": ("بنر در ربات", "نمایش داخل ربات‌های انتخاب‌شده"),
        "channel_post": ("پیام اسپانسری در کانال", "کاربران یا کانال‌های هدف"),
        "video_banner": ("بنر روی ویدیو", "فقط هدف‌گیری کاربران"),
    }
    verified = VERIFIED_TARGET_PLACEMENTS.get(target_type, frozenset())
    unverified = UNVERIFIED_TARGET_PLACEMENTS.get(target_type, frozenset())
    allowed = verified | unverified
    out: list[dict[str, Any]] = []
    for placement in sorted(allowed):
        title, hint = labels.get(placement, (placement, ""))
        out.append(
            {
                "placement": placement,
                "title_fa": title,
                "hint_fa": hint,
                "verified": placement in verified,
            }
        )
    return out


def resolve_api_placement(campaign_placement: str, target_type: str) -> str:
    """Map TMADS campaign.placement or API placement string to API placement."""
    if campaign_placement in API_PLACEMENTS:
        return campaign_placement
    api = TMADS_TO_API_PLACEMENT.get(campaign_placement, campaign_placement)
    if api in API_PLACEMENTS:
        return api
    return default_placement_for_target(target_type)


def validate_target_placement(target_type: str, placement: str) -> list[str]:
    errors: list[str] = []
    if target_type not in TARGET_TYPES:
        errors.append("نوع هدف‌گیری نامعتبر است.")
        return errors
    api_placement = resolve_api_placement(placement, target_type)
    if api_placement not in API_PLACEMENTS:
        errors.append("جایگاه نمایش با API سازگار نیست.")
        return errors
    verified = VERIFIED_TARGET_PLACEMENTS.get(target_type, frozenset())
    unverified = UNVERIFIED_TARGET_PLACEMENTS.get(target_type, frozenset())
    if api_placement not in verified and api_placement not in unverified:
        errors.append("این ترکیب هدف و جایگاه پشتیبانی نمی‌شود.")
    elif api_placement in unverified:
        errors.append("این جایگاه هنوز در حساب عملیات تأیید نشده است.")
    return errors
