from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.policies.constants import FindingSeverity


@dataclass
class PolicyFindingDTO:
    rule_id: str
    severity: str
    message_fa: str
    field_key: str = ""
    suggestion_fa: str = ""
    source_document: str = ""
    source_clause: str = ""
    source_url: str = ""
    requires_manual_review: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": str(self.severity),
            "message_fa": self.message_fa,
            "field_key": self.field_key,
            "suggestion_fa": self.suggestion_fa,
            "source_document": self.source_document,
            "source_clause": self.source_clause,
            "source_url": self.source_url,
            "requires_manual_review": self.requires_manual_review,
        }


@dataclass
class PolicyRunResult:
    findings: list[PolicyFindingDTO] = field(default_factory=list)
    policy_version_code: str = ""
    submission_ready: bool = False
    needs_manual_review: bool = False
    evaluation_id: str | None = None

    def counts(self) -> dict[str, int]:
        out = {s.value: 0 for s in FindingSeverity}
        for f in self.findings:
            out[f.severity] = out.get(f.severity, 0) + 1
        return out

    @property
    def blocked(self) -> bool:
        return any(f.severity == FindingSeverity.BLOCKED for f in self.findings)

    def findings_for_field(self, field_key: str) -> list[PolicyFindingDTO]:
        return [f for f in self.findings if f.field_key == field_key or not field_key]
