"""Read-only targeting catalogue with cache and safe fallbacks."""

from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache

from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError, TelegramAdsNotConfigured

logger = logging.getLogger(__name__)

CACHE_TTL = 3600

COUNTRY_FA: dict[str, str] = {
    "IR": "ایران",
    "DE": "آلمان",
    "US": "ایالات متحده",
    "GB": "بریتانیا",
    "TR": "ترکیه",
    "AE": "امارات",
    "FR": "فرانسه",
}

FALLBACK_COUNTRIES = [
    {"country_code": "IR", "name": "Iran", "name_fa": "ایران"},
    {"country_code": "DE", "name": "Germany", "name_fa": "آلمان"},
    {"country_code": "US", "name": "United States", "name_fa": "ایالات متحده"},
]

FALLBACK_LANGUAGES = [
    {"language_code": "fa", "name": "Persian"},
    {"language_code": "en", "name": "English"},
    {"language_code": "ru", "name": "Russian"},
]

FALLBACK_TOPICS = [
    {"topic_id": 1, "name": "Technology"},
    {"topic_id": 2, "name": "Business"},
    {"topic_id": 3, "name": "Entertainment"},
]


def _country_row(item: dict[str, Any]) -> dict[str, Any]:
    code = (item.get("country_code") or item.get("code") or "").upper()
    name = item.get("name") or code
    return {
        "country_code": code,
        "name": name,
        "name_fa": COUNTRY_FA.get(code, name),
    }


def get_countries() -> list[dict[str, Any]]:
    key = "tmads:catalog:countries:v1"
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows: list[dict[str, Any]] = []
    try:
        client = TelegramAdsClient()
        for item in client.get_target_countries():
            rows.append(_country_row(item))
    except (TelegramAdsError, TelegramAdsNotConfigured) as exc:
        logger.info("catalog countries fallback: %s", exc)
        rows = list(FALLBACK_COUNTRIES)
    except Exception:
        logger.exception("catalog countries error")
        rows = list(FALLBACK_COUNTRIES)
    if not rows:
        rows = list(FALLBACK_COUNTRIES)
    cache.set(key, rows, CACHE_TTL)
    return rows


def get_languages() -> list[dict[str, Any]]:
    key = "tmads:catalog:languages:v1"
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows: list[dict[str, Any]] = []
    try:
        client = TelegramAdsClient()
        for item in client.get_target_languages():
            rows.append(
                {
                    "language_code": item.get("language_code") or item.get("code") or "",
                    "name": item.get("name") or "",
                }
            )
    except (TelegramAdsError, TelegramAdsNotConfigured) as exc:
        logger.info("catalog languages fallback: %s", exc)
        rows = list(FALLBACK_LANGUAGES)
    except Exception:
        logger.exception("catalog languages error")
        rows = list(FALLBACK_LANGUAGES)
    cache.set(key, rows, CACHE_TTL)
    return rows


def get_topics() -> list[dict[str, Any]]:
    key = "tmads:catalog:topics:v1"
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows: list[dict[str, Any]] = []
    try:
        client = TelegramAdsClient()
        for item in client.get_target_topics():
            tid = item.get("topic_id") or item.get("id") or 0
            rows.append({"topic_id": int(tid), "name": item.get("name") or str(tid)})
    except (TelegramAdsError, TelegramAdsNotConfigured) as exc:
        logger.info("catalog topics fallback: %s", exc)
        rows = list(FALLBACK_TOPICS)
    except Exception:
        logger.exception("catalog topics error")
        rows = list(FALLBACK_TOPICS)
    cache.set(key, rows, CACHE_TTL)
    return rows


def search_locations(country_code: str, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
    country_code = (country_code or "").strip().upper()
    query = (query or "").strip()
    if len(country_code) != 2 or len(query) < 2:
        return []
    key = f"tmads:catalog:loc:{country_code}:{query.lower()[:32]}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows: list[dict[str, Any]] = []
    try:
        client = TelegramAdsClient()
        payload = client.get_target_locations(country_code, query, limit=limit)
        locations = payload.get("locations") or []
        for loc in locations:
            rows.append(
                {
                    "location_id": loc.get("location_id") or loc.get("id"),
                    "name": loc.get("name") or "",
                    "region": loc.get("region") or "",
                    "country_code": loc.get("country_code") or country_code,
                }
            )
    except (TelegramAdsError, TelegramAdsNotConfigured):
        if country_code == "IR" and ("تهر" in query or "teh" in query.lower()):
            rows = [{"location_id": 9001, "name": "Tehran", "region": "Tehran", "country_code": "IR"}]
    except Exception:
        logger.exception("location search failed")
    cache.set(key, rows, min(CACHE_TTL, 600))
    return rows


def resolve_bot(username: str) -> dict[str, Any]:
    username = (username or "").strip().lstrip("@")
    if not username:
        return {"ok": False, "error": "invalid"}
    try:
        client = TelegramAdsClient()
        data = client.get_target_bot(username)
        return {"ok": True, "bot": data}
    except (TelegramAdsError, TelegramAdsNotConfigured) as exc:
        return {"ok": False, "error": str(exc), "username": username, "pending": True}
    except Exception as exc:
        logger.exception("resolve_bot")
        return {"ok": False, "error": "unavailable", "username": username}


def resolve_channel(username: str) -> dict[str, Any]:
    username = (username or "").strip().lstrip("@")
    if not username:
        return {"ok": False, "error": "invalid"}
    try:
        client = TelegramAdsClient()
        data = client.get_target_channel(username)
        return {"ok": True, "channel": data}
    except (TelegramAdsError, TelegramAdsNotConfigured) as exc:
        return {"ok": False, "error": str(exc), "username": username, "pending": True}
    except Exception:
        logger.exception("resolve_channel")
        return {"ok": False, "error": "unavailable", "username": username}
