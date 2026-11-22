"""Build telead InputAdTarget objects from TMADS targeting config."""

from __future__ import annotations

from typing import Any

from telead.inputs import (
    InputAdTargetBots,
    InputAdTargetChannels,
    InputAdTargetSearch,
    InputAdTargetUsers,
)

from .normalize import normalize_search_query, normalize_username


def _peer_list(values: list[Any]) -> list[str | int]:
    peers: list[str | int] = []
    for raw in values or []:
        if isinstance(raw, int):
            peers.append(raw)
            continue
        s = str(raw).strip()
        if not s:
            continue
        if s.lstrip("-").isdigit():
            peers.append(int(s))
        else:
            peers.append(normalize_username(s))
    return peers


def build_input_target(target_type: str, config: dict[str, Any] | None) -> Any:
    cfg = config or {}
    if target_type == "search":
        queries = [
            normalize_search_query(q)
            for q in cfg.get("search_queries") or []
            if normalize_search_query(str(q))
        ]
        return InputAdTargetSearch(search_queries=queries)

    if target_type == "bots":
        return InputAdTargetBots(bot_ids=_peer_list(cfg.get("bot_ids") or []))

    if target_type == "channels":
        channel_ids = _peer_list(cfg.get("channel_ids") or [])
        topic_ids = [int(x) for x in cfg.get("topic_ids") or []]
        language_codes = [str(c) for c in cfg.get("language_codes") or []]
        if not language_codes and cfg.get("language_code"):
            language_codes = [str(cfg["language_code"])]
        exclude_topic_ids = [int(x) for x in cfg.get("exclude_topic_ids") or []]
        exclude_channel_ids = _peer_list(cfg.get("exclude_channel_ids") or [])
        # اولویت محدودیت API: کانال مشخص > موضوع+زبان > فقط زبان
        if channel_ids:
            return InputAdTargetChannels(
                channel_ids=channel_ids,
                exclude_channel_ids=exclude_channel_ids,
                exclude_topic_ids=exclude_topic_ids,
            )
        if topic_ids:
            return InputAdTargetChannels(
                language_codes=language_codes,
                topic_ids=topic_ids,
                exclude_topic_ids=exclude_topic_ids,
                exclude_channel_ids=exclude_channel_ids,
            )
        return InputAdTargetChannels(
            language_codes=language_codes,
            exclude_topic_ids=exclude_topic_ids,
            exclude_channel_ids=exclude_channel_ids,
        )

    if target_type == "users":
        return InputAdTargetUsers(
            country_codes=[str(c).upper() for c in cfg.get("country_codes") or []],
            location_ids=[int(x) for x in cfg.get("location_ids") or []],
            language_codes=[str(c) for c in cfg.get("language_codes") or []],
            topic_ids=[int(x) for x in cfg.get("topic_ids") or []],
            intersect_topics=bool(cfg.get("intersect_topics")),
            exclude_topic_ids=[int(x) for x in cfg.get("exclude_topic_ids") or []],
            channel_ids=_peer_list(cfg.get("channel_ids") or []),
            exclude_channel_ids=_peer_list(cfg.get("exclude_channel_ids") or []),
            audience_ids=[int(x) for x in cfg.get("audience_ids") or []],
            exclude_audience_ids=[int(x) for x in cfg.get("exclude_audience_ids") or []],
            device=cfg.get("device") or None,
            exclude_political_channels=bool(cfg.get("exclude_political_channels")),
            political_channels_only=bool(cfg.get("political_channels_only")),
        )

    raise ValueError(f"Unsupported target type: {target_type}")
