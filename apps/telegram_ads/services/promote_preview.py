"""Official Promote API preview for destination title/photo (no ads.telegram.org web session)."""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.core.cache import cache

from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import (
    TelegramAdsApiError,
    TelegramAdsError,
    TelegramAdsNotConfigured,
    TelegramAdsTransportError,
)
from apps.telegram_ads.targeting.normalize import parse_bot_peer_input

logger = logging.getLogger(__name__)

CACHE_TTL = 600
_HTTPS_PHOTO = re.compile(r"^https://[^\s<>\"']+$", re.IGNORECASE)
_TME = re.compile(
    r"(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/([A-Za-z0-9_]{3,32})",
    re.IGNORECASE,
)


def _safe_photo(url: Any) -> str:
    value = str(url or "").strip()
    return value[:500] if _HTTPS_PHOTO.fullmatch(value) else ""


def _photo_from_payload(data: dict[str, Any]) -> str:
    """Accept photo_url from model fields or nested raw / photo objects."""
    direct = _safe_photo(data.get("photo_url"))
    if direct:
        return direct
    raw = data.get("raw") if isinstance(data.get("raw"), dict) else {}
    nested = _safe_photo(raw.get("photo_url"))
    if nested:
        return nested
    photo = data.get("photo")
    if isinstance(photo, dict):
        return _safe_photo(photo.get("photo_url") or photo.get("url"))
    return ""


def _safe_title(value: Any, fallback: str = "") -> str:
    text = re.sub(r"<[^>]*>", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return (text or fallback)[:120]


def _looks_like_bot(username: str, destination: str) -> bool:
    if username.casefold().endswith("bot"):
        return True
    raw = destination.strip()
    try:
        parsed = urlparse(raw if "://" in raw else f"https://{raw.lstrip('/')}")
        query = parse_qs(parsed.query)
        if query.get("start") or query.get("startapp"):
            return True
    except ValueError:
        pass
    return False


def _extract_username(destination: str) -> str | None:
    at, _ = parse_bot_peer_input(destination)
    if at:
        return at
    match = _TME.search(destination or "")
    if match:
        return f"@{match.group(1)}"
    return None


def resolve_promote_preview(destination: str) -> dict[str, Any]:
    """Return clean preview metadata for a promote URL via getTargetBot / getTargetChannel."""
    dest = (destination or "").strip()[:500]
    username = _extract_username(dest)
    if not username:
        return {
            "ok": False,
            "reason": "invalid_destination",
            "message_fa": "مقصد تلگرامی معتبری پیدا نشد.",
            "title": "",
            "username": None,
            "photo_url": "",
            "kind": None,
        }

    scope = hashlib.sha256(settings.TELEGRAM_ADS_API_TOKEN.encode()).hexdigest()[:16]
    cache_key = f"tmads:promote_preview:v1:{scope}:{username.casefold()}"
    cached = cache.get(cache_key)
    if isinstance(cached, dict):
        return cached

    kind = "bot" if _looks_like_bot(username.lstrip("@"), dest) else "channel"
    client = TelegramAdsClient()
    try:
        if kind == "bot":
            data = client.resolve_target_bot(username)
            title = _safe_title(data.get("title"), username.lstrip("@"))
            photo = _photo_from_payload(data)
            peer_ok = isinstance(data.get("bot_id"), int) and data["bot_id"] > 0
        else:
            data = client.resolve_target_channel(username)
            title = _safe_title(data.get("title"), username.lstrip("@"))
            photo = _photo_from_payload(data)
            # شناسه کانال تلگرام معمولاً منفی است (−100…).
            peer_ok = isinstance(data.get("channel_id"), int) and data["channel_id"] != 0
            # Some destinations end without "bot" but are bots — soft fallback.
            if not peer_ok:
                try:
                    data = client.resolve_target_bot(username)
                    if isinstance(data.get("bot_id"), int) and data["bot_id"] > 0:
                        kind = "bot"
                        title = _safe_title(data.get("title"), username.lstrip("@"))
                        photo = _photo_from_payload(data)
                        peer_ok = True
                except TelegramAdsError:
                    pass
    except TelegramAdsNotConfigured:
        return {
            "ok": False,
            "reason": "api_unavailable",
            "message_fa": "بررسی مقصد فعلاً ممکن نیست.",
            "title": username.lstrip("@"),
            "username": username,
            "photo_url": "",
            "kind": kind,
        }
    except (TelegramAdsTransportError, TelegramAdsApiError, TelegramAdsError):
        logger.info("promote preview resolve failed for %s", username)
        return {
            "ok": False,
            "reason": "resolve_failed",
            "message_fa": "عکس مقصد دریافت نشد.",
            "title": username.lstrip("@"),
            "username": username,
            "photo_url": "",
            "kind": kind,
        }
    except Exception:
        logger.exception("promote preview unexpected error")
        return {
            "ok": False,
            "reason": "internal",
            "message_fa": "خطای داخلی پیش‌نمایش.",
            "title": username.lstrip("@"),
            "username": username,
            "photo_url": "",
            "kind": kind,
        }

    payload = {
        "ok": bool(peer_ok),
        "reason": "ok" if peer_ok else "unresolved",
        "message_fa": "",
        "title": title,
        "username": username,
        "photo_url": photo,
        "kind": kind,
    }
    if peer_ok:
        cache.set(cache_key, payload, CACHE_TTL)
    return payload
