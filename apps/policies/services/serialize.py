from __future__ import annotations

import re

from django.urls import reverse

from apps.policies.services.rules_registry import guide_anchor_for, rule_meta
from apps.policies.services.types import PolicyFindingDTO

_PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_CLAUSE_ALIASES = {
    "acceptance": "پذیرش شرایط",
    "customer acceptance": "پذیرش شرایط",
}


def format_clause_label(raw: str | None) -> str:
    """Human-readable Persian clause badge; avoid § which reverses in RTL."""
    text = str(raw or "").strip()
    if not text:
        return ""
    text = text.lstrip("§").strip()
    alias = _CLAUSE_ALIASES.get(text.lower())
    if alias:
        return alias
    # Numeric Telegram guideline sections: 5.6 / 4.3 / 3.3(e)
    if re.fullmatch(r"\d+(?:\.\d+)*(?:\([a-z]\))?", text, flags=re.I):
        return f"بند {text.translate(_PERSIAN_DIGITS)}"
    # Already Persian-friendly clause text from registry
    if re.search(r"[\u0600-\u06FF]", text):
        return text if text.startswith("بند") else f"بند {text}"
    return text


def serialize_policy_finding(finding: PolicyFindingDTO) -> dict:
    meta = rule_meta(finding.rule_id)
    data = finding.to_dict()
    title_fa = meta.get("title_fa") or finding.rule_id
    data["rule_title_fa"] = title_fa
    clause_raw = finding.source_clause or meta.get("clause") or ""
    data["source_clause_label"] = format_clause_label(clause_raw)

    if finding.rule_id == "TMADS-ACC-001":
        data["source_clause_label"] = "پذیرش شرایط"
        data["guide_url"] = reverse("public:terms")
        data["guide_label"] = "مشاهده شرایط گرام‌ادز"
        return data

    anchor = guide_anchor_for(finding.rule_id, finding.source_clause)
    if anchor:
        data["guide_url"] = f"{reverse('policies:ad_policies')}#{anchor}"
        data["guide_label"] = f"مشاهده قانون: {title_fa}"
    elif finding.source_url:
        data["guide_url"] = finding.source_url
        data["guide_label"] = "مشاهده منبع رسمی"
    else:
        data["guide_url"] = reverse("policies:ad_policies")
        data["guide_label"] = "راهنمای کامل قوانین"
    return data
