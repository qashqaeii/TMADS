from __future__ import annotations

import re

from apps.campaigns.models import Campaign
from apps.policies.constants import FindingSeverity
from apps.policies.services.rules_registry import rule_meta
from apps.policies.services.types import PolicyFindingDTO

_SENSITIVE_BAIT = re.compile(
    r"(جنگ|بمب|ترور|مواد|مشروب|شرط\s*بندی|کازینو|سکه\s*حرام|جنس|پورن|اسلحه)",
    re.IGNORECASE,
)
_MISLEADING_SUPER = re.compile(
    r"(بهترین|برترین|تضمین|۱۰۰٪|۱۰۰%|سود\s*قطعی|ثروتمند|میلیونر|کلیک\s*کن|برد\s*کردی)",
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


def check_targeting(campaign: Campaign, config: dict | None, ad_text: str = "") -> list[PolicyFindingDTO]:
    findings: list[PolicyFindingDTO] = []
    target_type = campaign.target_type or ""
    cfg = config or {}

    if target_type == "search":
        queries = cfg.get("search_queries") or []
        for q in queries:
            if _SENSITIVE_BAIT.search(q or ""):
                findings.append(
                    _meta(
                        "TG-DST-004",
                        severity=FindingSeverity.REVIEW_REQUIRED,
                        field_key="search_queries",
                        message_fa=f"عبارت جستجوی «{q}» ممکن است موضوع حساس یا ممنوع را هدف بگیرد.",
                        requires_manual_review=True,
                    )
                )
            if _MISLEADING_SUPER.search(q or ""):
                findings.append(
                    _meta(
                        "TG-EDI-002",
                        severity=FindingSeverity.WARNING,
                        field_key="search_queries",
                        message_fa="عبارت جستجو با ادبیات اغراق‌آمیز ممکن است رد شود.",
                    )
                )

    ad_langs = set(cfg.get("language_codes") or [])
    if ad_langs and len(ad_langs) > 1:
        findings.append(
            _meta(
                "TG-DST-004",
                severity=FindingSeverity.INFO,
                field_key="language_codes",
                message_fa="زبان هدف‌گیری و زبان تبلیغ بهتر است هم‌خوان باشند.",
            )
        )

    text = (ad_text or "").strip()
    if text and _MISLEADING_SUPER.search(text):
        findings.append(
            _meta(
                "TG-PRH-005",
                severity=FindingSeverity.REVIEW_REQUIRED,
                field_key="ad_text",
                message_fa="این جمله ممکن است یک ادعای اثبات‌نشده باشد. پیشنهاد می‌کنیم آن را دقیق‌تر بنویسید.",
                requires_manual_review=True,
            )
        )

    return findings
