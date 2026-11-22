"""Rule metadata for traceability — not a reproduction of Telegram legal text."""

from __future__ import annotations

from typing import Any

from apps.policies.constants import SOURCE_ADS_TOS, SOURCE_GETTING_STARTED, SOURCE_GUIDELINES

RuleMeta = dict[str, Any]

RULES: dict[str, RuleMeta] = {
    "TG-FMT-001": {
        "document": "Telegram Ad Guidelines",
        "clause": "§1 Ad format",
        "url": SOURCE_GUIDELINES,
        "auto": True,
        "manual": False,
        "targets": ("search", "bots", "users", "channels"),
    },
    "TG-EDI-002": {
        "document": "Telegram Ad Guidelines",
        "clause": "§2 Editorial requirements",
        "url": SOURCE_GUIDELINES,
        "auto": True,
        "manual": True,
        "targets": ("bots", "users", "channels"),
    },
    "TG-LNK-003": {
        "document": "Telegram Ad Guidelines",
        "clause": "§3 Link format",
        "url": SOURCE_GUIDELINES,
        "auto": True,
        "manual": False,
        "targets": ("bots", "users", "channels"),
    },
    "TG-DST-004": {
        "document": "Telegram Ad Guidelines",
        "clause": "§4 Destination and targeting",
        "url": SOURCE_GUIDELINES,
        "auto": True,
        "manual": True,
        "targets": ("search", "bots", "users", "channels"),
    },
    "TG-PRH-005": {
        "document": "Telegram Ad Guidelines",
        "clause": "§5 Prohibited content",
        "url": SOURCE_GUIDELINES,
        "auto": False,
        "manual": True,
        "targets": ("search", "bots", "users", "channels"),
    },
    "TG-TOS-006": {
        "document": "Telegram Ad Platform ToS",
        "clause": "§3.3(e) third-party bidding",
        "url": SOURCE_ADS_TOS,
        "auto": True,
        "manual": True,
        "targets": (),
    },
    "TG-TOS-007": {
        "document": "Telegram Ad Platform ToS",
        "clause": "§4.3 unspent balance",
        "url": SOURCE_ADS_TOS,
        "auto": False,
        "manual": False,
        "targets": (),
    },
    "TG-GSG-008": {
        "document": "Getting Started",
        "clause": "External links vs t.me",
        "url": SOURCE_GETTING_STARTED,
        "auto": True,
        "manual": True,
        "targets": ("bots", "users", "channels"),
    },
    "TMADS-ACC-001": {
        "document": "GramAds Terms",
        "clause": "Customer acceptance",
        "url": "/terms/",
        "auto": True,
        "manual": False,
        "targets": ("search", "bots", "users", "channels"),
    },
}


def rule_meta(rule_id: str) -> RuleMeta:
    return RULES.get(rule_id, {"document": "", "clause": "", "url": "", "auto": False, "manual": True, "targets": ()})
