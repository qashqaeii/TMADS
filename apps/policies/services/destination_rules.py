from __future__ import annotations

from apps.campaigns.models import Campaign
from apps.policies.constants import FindingSeverity
from apps.policies.services.rules_registry import rule_meta
from apps.policies.services.types import PolicyFindingDTO


def _meta(rule_id: str, **kwargs) -> PolicyFindingDTO:
    meta = rule_meta(rule_id)
    return PolicyFindingDTO(
        rule_id=rule_id,
        source_document=meta.get("document", ""),
        source_clause=meta.get("clause", ""),
        source_url=meta.get("url", ""),
        **kwargs,
    )


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

    is_bot = "/bot" in dest or campaign.objective == "bot"
    is_channel = campaign.objective == "channel" or campaign.target_type == "channels"

    if not settings.get("destination_rights_confirmed"):
        findings.append(
            _meta(
                "TMADS-ACC-001",
                severity=FindingSeverity.REVIEW_REQUIRED,
                field_key="destination",
                message_fa="لطفاً تأیید کنید حق قانونی تبلیغ این مقصد را دارید.",
                requires_manual_review=True,
            )
        )

    if is_channel or (dest and "t.me" in dest and not is_bot):
        if not settings.get("channel_active_confirmed"):
            findings.append(
                _meta(
                    "TG-DST-004",
                    severity=FindingSeverity.WARNING,
                    field_key="destination",
                    message_fa="برای تأیید تبلیغ، کانال باید فعال باشد و در دو هفته اخیر حداقل یک پست منتشر کرده باشد.",
                    suggestion_fa="در مرحلهٔ محتوا گزینهٔ تأیید فعالیت کانال را علامت بزنید یا با پشتیبانی هماهنگ کنید.",
                )
            )

    if is_bot:
        checklist = {
            "bot_has_photo": "تصویر پروفایل ربات",
            "bot_has_description": "توضیحات ربات",
            "bot_functional_confirmed": "کارکرد ربات روی موبایل و دسکتاپ",
        }
        missing = [label for key, label in checklist.items() if not settings.get(key)]
        if missing:
            findings.append(
                _meta(
                    "TG-DST-004",
                    severity=FindingSeverity.WARNING,
                    field_key="destination",
                    message_fa="آمادگی ربات ناقص است: " + "، ".join(missing) + ".",
                )
            )

    if not any(settings.get(k) for k in ("profile_complete_confirmed", "channel_active_confirmed", "bot_functional_confirmed")):
        findings.append(
            _meta(
                "TG-DST-004",
                severity=FindingSeverity.INFO,
                field_key="destination",
                message_fa="محتوای پروفایل و About مقصد باید کامل باشد (طبق دستورالعمل تلگرام).",
            )
        )

    return findings
