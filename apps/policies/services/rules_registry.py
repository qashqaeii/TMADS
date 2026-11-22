"""Rule metadata for traceability — not a reproduction of Telegram legal text."""

from __future__ import annotations

from typing import Any

from apps.policies.constants import SOURCE_ADS_TOS, SOURCE_GETTING_STARTED, SOURCE_GUIDELINES

RuleMeta = dict[str, Any]

RULES: dict[str, RuleMeta] = {
    "TG-FMT-001": {
        "document": "Telegram Ad Guidelines",
        "clause": "§1 قالب تبلیغ",
        "title_fa": "قالب و محدودیت متن",
        "guide_section": "text",
        "url": SOURCE_GUIDELINES,
        "auto": True,
        "manual": False,
        "targets": ("search", "bots", "users", "channels"),
    },
    "TG-EDI-002": {
        "document": "Telegram Ad Guidelines",
        "clause": "§2 الزامات ویرایشی",
        "title_fa": "الزامات ویرایشی متن",
        "guide_section": "text",
        "url": SOURCE_GUIDELINES,
        "auto": True,
        "manual": True,
        "targets": ("bots", "users", "channels"),
    },
    "TG-LNK-003": {
        "document": "Telegram Ad Guidelines",
        "clause": "§3 فرمت لینک",
        "title_fa": "لینک و مقصد تبلیغ",
        "guide_section": "destination",
        "url": SOURCE_GUIDELINES,
        "auto": True,
        "manual": False,
        "targets": ("bots", "users", "channels"),
    },
    "TG-DST-004": {
        "document": "Telegram Ad Guidelines",
        "clause": "§4 مقصد و هدف‌گیری",
        "title_fa": "ربات، کانال و آمادگی مقصد",
        "guide_section": "bots_channels",
        "url": SOURCE_GUIDELINES,
        "auto": True,
        "manual": True,
        "targets": ("search", "bots", "users", "channels"),
    },
    "TG-PRH-005": {
        "document": "Telegram Ad Guidelines",
        "clause": "§5 محتوای غیرمجاز",
        "title_fa": "محتوای حساس و غیرمجاز",
        "guide_section": "prohibited",
        "url": SOURCE_GUIDELINES,
        "auto": False,
        "manual": True,
        "targets": ("search", "bots", "users", "channels"),
    },
    "TG-TOS-006": {
        "document": "Telegram Ad Platform ToS",
        "clause": "§3.3(e) پیشنهاد شخص ثالث",
        "title_fa": "مجوز حساب مرکزی",
        "guide_section": "",
        "url": SOURCE_ADS_TOS,
        "auto": True,
        "manual": True,
        "targets": (),
    },
    "TG-TOS-007": {
        "document": "Telegram Ad Platform ToS",
        "clause": "§4.3 اعتبار مصرف‌نشده",
        "title_fa": "بودجه و اعتبار تبلیغ",
        "guide_section": "budget",
        "url": SOURCE_ADS_TOS,
        "auto": False,
        "manual": False,
        "targets": (),
    },
    "TG-GSG-008": {
        "document": "Getting Started",
        "clause": "لینک خارجی در برابر t.me",
        "title_fa": "لینک و مقصد تبلیغ",
        "guide_section": "destination",
        "url": SOURCE_GETTING_STARTED,
        "auto": True,
        "manual": True,
        "targets": ("bots", "users", "channels"),
    },
    "TMADS-ACC-001": {
        "document": "GramAds Terms",
        "clause": "پذیرش مشتری",
        "title_fa": "پذیرش شرایط گرام‌ادز",
        "guide_section": "",
        "url": "/terms/",
        "auto": True,
        "manual": False,
        "targets": ("search", "bots", "users", "channels"),
    },
}

# Sub-anchors inside the prohibited guide section (Telegram §5.x).
PROHIBITED_GUIDE_ANCHORS = {
    "5.6": "gambling",
    "5.7": "finance",
    "5.9": "substances",
    "5.10": "weapons",
    "5.11": "malware",
}


def rule_meta(rule_id: str) -> RuleMeta:
    return RULES.get(
        rule_id,
        {
            "document": "",
            "clause": "",
            "title_fa": "",
            "guide_section": "",
            "url": "",
            "auto": False,
            "manual": True,
            "targets": (),
        },
    )


def guide_anchor_for(rule_id: str, source_clause: str = "") -> str:
    meta = rule_meta(rule_id)
    section = meta.get("guide_section") or ""
    if not section:
        return ""
    clause = (source_clause or "").lstrip("§").strip()
    if rule_id == "TG-PRH-005" and clause in PROHIBITED_GUIDE_ANCHORS:
        return f"policy-{section}-{PROHIBITED_GUIDE_ANCHORS[clause]}"
    return f"policy-{section}"
