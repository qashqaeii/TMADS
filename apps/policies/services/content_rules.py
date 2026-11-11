from __future__ import annotations

import re

from apps.policies.constants import FindingSeverity, SOURCE_GUIDELINES
from apps.policies.services.rules_registry import rule_meta
from apps.policies.services.types import PolicyFindingDTO

# Advisory hints only — never sole basis for automatic rejection.
_CATEGORY_HINTS: list[tuple[str, re.Pattern[str], str]] = [
    ("5.6", re.compile(r"(کازینو|شرط\s*بندی|پوکر|بت|اسلات)", re.I), "ممکن است در دستهٔ قمار قرار گیرد."),
    ("5.7", re.compile(r"(سود\s*مضمون|پیش\s*بینی\s*قطعی|وام\s*فوری|هر\s*روز\s*درآمد)", re.I), "ممکن است در دستهٔ خدمات مالی پرریسک قرار گیرد."),
    ("5.9", re.compile(r"(سیگار|ویپ|الکل|مشروب|حشیش|شیشه)", re.I), "ممکن است در دستهٔ الکل/دخانیات/مواد قرار گیرد."),
    ("5.10", re.compile(r"(اسلحه|کلت|تفنگ|گلوله|مواد\s*منفجره)", re.I), "ممکن است در دستهٔ سلاح قرار گیرد."),
    ("5.11", re.compile(r"(هک|کرک|فیشینگ|فالوور\s*ارزان|لایک\s*رایگان)", re.I), "ممکن است در دستهٔ اسپم/بدافزار قرار گیرد."),
]


def scan_prohibited_hints(ad_text: str | None, title: str = "") -> list[PolicyFindingDTO]:
    blob = f"{title}\n{ad_text or ''}".strip()
    if not blob:
        return []
    findings: list[PolicyFindingDTO] = []
    for section, pattern, hint in _CATEGORY_HINTS:
        if pattern.search(blob):
            meta = rule_meta("TG-PRH-005")
            findings.append(
                PolicyFindingDTO(
                    rule_id="TG-PRH-005",
                    severity=FindingSeverity.REVIEW_REQUIRED,
                    field_key="ad_text",
                    message_fa=f"محتوا با موضوعات حساس مرتبط است — {hint}",
                    source_document=meta.get("document", "Telegram Ad Guidelines"),
                    source_clause=f"§5.{section}",
                    source_url=SOURCE_GUIDELINES,
                    requires_manual_review=True,
                    suggestion_fa="اگر تبلیغ آموزشی یا بی‌خطر است، در توضیحات برای پشتیبانی بنویسید.",
                )
            )
    return findings
