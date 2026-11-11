"""Telegram Ads API constants aligned with docs/Telegramads-API-INFORMATION.md."""

from __future__ import annotations

# API placement strings (createAd.placement)
API_PLACEMENTS = frozenset(
    {
        "channel_post",
        "bot_banner",
        "search_result",
        "video_banner",
    }
)

# Campaign.placement (TMADS) -> API placement
TMADS_TO_API_PLACEMENT = {
    "search_result": "search_result",
    "bot_banner": "bot_banner",
    "channels": "channel_post",
    "video": "video_banner",
}

API_TO_TMADS_PLACEMENT = {v: k for k, v in TMADS_TO_API_PLACEMENT.items()}

API_AD_STATUSES = frozenset(
    {
        "stopped",
        "ready_for_review",
        "in_review",
        "declined",
        "active",
        "on_hold",
    }
)

STATS_INTERVAL_DAY = 86400
STATS_INTERVAL_5MIN = 300
