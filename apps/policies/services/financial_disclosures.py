from __future__ import annotations

from apps.policies.constants import FindingSeverity, SOURCE_ADS_TOS
from apps.policies.services.types import PolicyFindingDTO


def budget_step_guidance() -> list[PolicyFindingDTO]:
    """Non-blocking customer education (TMADS wallet vs Telegram balance)."""
    return [
        PolicyFindingDTO(
            rule_id="TG-TOS-007",
            severity=FindingSeverity.INFO,
            field_key="budget",
            message_fa="موجودی رزرو شده در TMADS با اعتبار تبلیغاتی حساب تلگرام اپراتور متفاوت است؛ بازپرداخت طبق قرارداد TMADS است نه مستقیماً از تلگرام.",
            source_document="Telegram Ad Platform ToS",
            source_clause="§4.3",
            source_url=SOURCE_ADS_TOS,
        ),
        PolicyFindingDTO(
            rule_id="TG-TOS-007",
            severity=FindingSeverity.INFO,
            field_key="budget",
            message_fa="CPM و نمایش تضمین‌شده نیست؛ تلگرام می‌تواند تبلیغ را رد یا متوقف کند.",
            source_document="Telegram Ad Platform ToS",
            source_clause="§5.2",
            source_url=SOURCE_ADS_TOS,
        ),
    ]
