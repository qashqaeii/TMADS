"""Normalize user-entered Telegram peers and search queries."""

from __future__ import annotations

import re
from urllib.parse import urlparse


_TME_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me)/(?P<name>[A-Za-z0-9_]{4,32})",
    re.IGNORECASE,
)


def normalize_username(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    m = _TME_RE.search(raw)
    if m:
        return f"@{m.group('name')}"
    if raw.startswith("@"):
        return f"@{raw.lstrip('@')}"
    if re.fullmatch(r"[A-Za-z0-9_]{4,32}", raw):
        return f"@{raw}"
    return raw


def parse_bot_peer_input(value: str) -> tuple[str | None, str | None]:
    """Return ``(@username, api_peer)`` for getTargetBot or ``(None, None)`` if invalid.

    ``api_peer`` is passed to telead as ``@username`` (official API format).
    """
    at = normalize_username(value)
    if not at or not re.fullmatch(r"@[A-Za-z0-9_]{4,32}", at):
        return None, None
    return at, at


def normalize_search_query(value: str) -> str:
    return " ".join((value or "").strip().split())


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def parse_promote_url(value: str) -> tuple[str, list[str]]:
    """Return (normalized_url, errors)."""
    errors: list[str] = []
    url = (value or "").strip()
    if not url:
        errors.append("آدرس مقصد تبلیغ الزامی است.")
        return "", errors
    if url.startswith("@"):
        url = f"https://t.me/{url.lstrip('@')}"
    elif re.fullmatch(r"[A-Za-z0-9_]{4,32}", url):
        url = f"https://t.me/{url}"
    if not url.startswith(("http://", "https://", "tg://")):
        if "t.me/" in url:
            url = "https://" + url.lstrip("/")
        else:
            errors.append("فرمت لینک مقصد معتبر نیست.")
            return url, errors
    if len(url) > 256:
        errors.append("لینک مقصد بیش از حد مجاز است.")
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https", "tg"}:
        errors.append("فقط لینک https یا tg:// پذیرفته می‌شود.")
    return url, errors
