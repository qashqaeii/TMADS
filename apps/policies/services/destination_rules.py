from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from apps.campaigns.models import Campaign
from apps.policies.constants import FindingSeverity
from apps.policies.services.rules_registry import rule_meta
from apps.policies.services.types import PolicyFindingDTO

_TME_USERNAME = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]{4,32})",
    re.IGNORECASE,
)


def _meta(rule_id: str, **kwargs) -> PolicyFindingDTO:
    meta = rule_meta(rule_id)
    return PolicyFindingDTO(
        rule_id=rule_id,
        source_document=meta.get("document", ""),
        source_clause=meta.get("clause", ""),
        source_url=meta.get("url", ""),
        **kwargs,
    )


def _telegram_username(dest: str) -> str:
    match = _TME_USERNAME.search(dest or "")
    return (match.group(1) if match else "").lower()


def destination_looks_like_bot(campaign: Campaign) -> bool:
    """Detect Telegram bot destinations (username ends with bot, start deep-link, or objective)."""
    if campaign.objective == Campaign.Objective.BOT:
        return True
    dest = (campaign.destination or "").strip()
    if not dest:
        return False
    lower = dest.lower()
    parsed = urlparse(lower if "://" in lower else f"https://{lower.lstrip('/')}")
    query = parse_qs(parsed.query)
    if query.get("start") or query.get("startapp"):
        return True
    username = _telegram_username(dest)
    if username.endswith("bot"):
        return True
    return False


def check_destination_readiness(campaign: Campaign) -> list[PolicyFindingDTO]:
    findings: list[PolicyFindingDTO] = []
    settings = campaign.ad_settings or {}
    dest = (campaign.destination or "").strip().lower()

    if not dest:
        findings.append(
            _meta(
                "TG-DST-004",
                severity=FindingSeverity.BLOCKED,
                field_key="destination",
                message_fa="مقصد تبلیغ تنظیم نشده است.",
            )
        )
        return findings

    is_bot = destination_looks_like_bot(campaign)
    is_channel = (
        campaign.objective == Campaign.Objective.CHANNEL
        or (campaign.target_type == Campaign.TargetType.CHANNELS and not is_bot)
    )
    is_telegram_peer = "t.me" in dest or "telegram.me" in dest

    if not settings.get("destination_rights_confirmed"):
        findings.append(
            _meta(
                "TMADS-ACC-001",
                severity=FindingSeverity.REVIEW_REQUIRED,
                field_key="destination_rights_confirmed",
                message_fa="لطفاً تأیید کنید حق قانونی تبلیغ این مقصد را دارید.",
                suggestion_fa="همین پایین، کنار لینک مقصد، گزینهٔ «حق تبلیغ این مقصد رو دارم» را علامت بزنید.",
                requires_manual_review=True,
            )
        )

    # Channel activity applies to channels only — never to bot deep-links/usernames.
    if (is_channel or (is_telegram_peer and not is_bot)) and not settings.get("channel_active_confirmed"):
        findings.append(
            _meta(
                "TG-DST-004",
                severity=FindingSeverity.WARNING,
                field_key="channel_active_confirmed",
                message_fa="برای تأیید تبلیغ، کانال باید فعال باشد و در دو هفته اخیر حداقل یک پست منتشر کرده باشد.",
                suggestion_fa="در مرحلهٔ محتوا گزینهٔ تأیید فعالیت کانال را علامت بزنید یا با پشتیبانی هماهنگ کنید.",
            )
        )

    if is_bot and not settings.get("bot_functional_confirmed"):
        findings.append(
            _meta(
                "TG-DST-004",
                severity=FindingSeverity.WARNING,
                field_key="bot_functional_confirmed",
                message_fa="اگر مقصد ربات است، روی موبایل و دسکتاپ باید درست کار کند.",
                suggestion_fa="در مرحلهٔ محتوا گزینهٔ تأیید کارکرد ربات را علامت بزنید.",
            )
        )

    if not any(
        settings.get(k)
        for k in ("profile_complete_confirmed", "channel_active_confirmed", "bot_functional_confirmed")
    ):
        findings.append(
            _meta(
                "TG-DST-004",
                severity=FindingSeverity.INFO,
                field_key="profile_complete_confirmed",
                message_fa="محتوای پروفایل و About مقصد باید کامل باشد (طبق دستورالعمل تلگرام).",
                suggestion_fa="در مرحلهٔ محتوا گزینهٔ کامل بودن پروفایل مقصد را علامت بزنید.",
            )
        )

    return findings
