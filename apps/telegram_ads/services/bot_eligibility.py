"""Target-bot resolution and eligibility classification (official getTargetBot only)."""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

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

EligibilityState = Literal[
    "eligible",
    "insufficient_audience",
    "invalid_bot",
    "unknown",
    "api_unavailable",
]

CACHE_TTL_SECONDS = 300

_MSG_INSUFFICIENT = "این ربات حداقل مخاطب لازم برای نمایش تبلیغ را ندارد."
_MSG_UNKNOWN = "ربات شناسایی شد؛ واجد شرایط بودن آن هنوز تأیید نشده است."
_MSG_UNAVAILABLE = "بررسی ربات در حال حاضر امکان‌پذیر نیست."
_MSG_INVALID = "نام کاربری ربات معتبر نیست یا توسط تلگرام شناسایی نشد."
_MSG_ELIGIBLE = "ربات برای هدف‌گیری تبلیغاتی تأیید شد."

_INSUFFICIENT_CODES = frozenset({"BOT_TOO_SMALL"})
_INVALID_CODES = frozenset(
    {
        "BOT_ID_INVALID",
        "BOT_ID_UNKNOWN",
        "USERNAME_INVALID",
        "USERNAME_NOT_OCCUPIED",
        "PEER_ID_INVALID",
    }
)
_INSUFFICIENT_TEXT = re.compile(
    r"1000\+?\s*daily|daily\s+users|BOT_TOO_SMALL",
    re.IGNORECASE,
)


@dataclass
class BotMetadata:
    bot_id: int | None = None
    title: str | None = None
    username: str | None = None
    photo_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class BotEligibilityResult:
    ok: bool
    query: str
    username: str | None
    eligibility: EligibilityState
    message_fa: str
    hard_block: bool = False
    verified: bool = False
    bot: dict[str, Any] = field(default_factory=dict)
    api_code: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "query": self.query,
            "username": self.username,
            "eligibility": self.eligibility,
            "message_fa": self.message_fa,
            "hard_block": self.hard_block,
            "verified": self.verified,
            "bot": self.bot,
            "api_code": self.api_code,
        }


def _cache_key(username: str) -> str:
    return f"tmads:bot_elig:v1:{username.casefold().lstrip('@')}"


def _metadata_from_payload(data: dict[str, Any]) -> BotMetadata:
    raw = data.get("raw") if isinstance(data.get("raw"), dict) else data
    username = data.get("username") or raw.get("username")
    if username and not str(username).startswith("@"):
        username = f"@{username}"
    return BotMetadata(
        bot_id=data.get("bot_id") or raw.get("bot_id"),
        title=data.get("title") or raw.get("title"),
        username=username,
        photo_url=data.get("photo_url") or raw.get("photo_url"),
    )


def _classify_api_error(code: str | None, description: str | None = None) -> BotEligibilityResult:
    code_u = (code or "").upper()
    desc = (description or "")[:500]
    if code_u in _INSUFFICIENT_CODES or _INSUFFICIENT_TEXT.search(f"{code_u} {desc}"):
        return BotEligibilityResult(
            ok=False,
            query="",
            username=None,
            eligibility="insufficient_audience",
            message_fa=_MSG_INSUFFICIENT,
            hard_block=True,
            verified=True,
            api_code=code_u or "BOT_TOO_SMALL",
        )
    if code_u in _INVALID_CODES:
        return BotEligibilityResult(
            ok=False,
            query="",
            username=None,
            eligibility="invalid_bot",
            message_fa=_MSG_INVALID,
            hard_block=False,
            verified=True,
            api_code=code_u,
        )
    if code_u.endswith(("_DENIED", "_DISABLED", "_FORBIDDEN")) or code_u.startswith("ACCESS_TOKEN_"):
        return BotEligibilityResult(
            ok=False,
            query="",
            username=None,
            eligibility="api_unavailable",
            message_fa=_MSG_UNAVAILABLE,
            hard_block=False,
            verified=False,
            api_code=code_u,
        )
    return BotEligibilityResult(
        ok=False,
        query="",
        username=None,
        eligibility="unknown",
        message_fa=_MSG_UNKNOWN,
        hard_block=False,
        verified=False,
        api_code=code_u or None,
    )


def check_bot_eligibility(value: str, *, use_cache: bool = True) -> BotEligibilityResult:
    """Resolve bot metadata and classify eligibility via official ``getTargetBot``."""
    query = (value or "").strip()
    username_at, api_peer = parse_bot_peer_input(query)
    if not username_at or not api_peer:
        return BotEligibilityResult(
            ok=False,
            query=query,
            username=None,
            eligibility="invalid_bot",
            message_fa=_MSG_INVALID,
            hard_block=False,
            verified=True,
        )

    if use_cache:
        cached = cache.get(_cache_key(username_at))
        if isinstance(cached, dict):
            cached["query"] = query
            return BotEligibilityResult(**{**cached, "query": query})

    try:
        client = TelegramAdsClient()
        data = client.resolve_target_bot(api_peer)
    except TelegramAdsNotConfigured:
        return BotEligibilityResult(
            ok=False,
            query=query,
            username=username_at,
            eligibility="api_unavailable",
            message_fa=_MSG_UNAVAILABLE,
            hard_block=False,
            verified=False,
        )
    except TelegramAdsTransportError:
        return BotEligibilityResult(
            ok=False,
            query=query,
            username=username_at,
            eligibility="api_unavailable",
            message_fa=_MSG_UNAVAILABLE,
            hard_block=False,
            verified=False,
        )
    except TelegramAdsApiError as exc:
        base = _classify_api_error(exc.api_code, exc.description)
        base.query = query
        base.username = username_at
        if use_cache and base.eligibility in {"insufficient_audience", "invalid_bot"}:
            cache.set(_cache_key(username_at), _result_cache_payload(base), CACHE_TTL_SECONDS)
        return base
    except TelegramAdsError as exc:
        logger.warning("bot eligibility unexpected telegram error: %s", exc)
        return BotEligibilityResult(
            ok=False,
            query=query,
            username=username_at,
            eligibility="api_unavailable",
            message_fa=_MSG_UNAVAILABLE,
            hard_block=False,
            verified=False,
        )
    except Exception:
        logger.exception("bot eligibility internal error for query=%r", query[:64])
        raise

    meta = _metadata_from_payload(data)
    bot_payload = meta.to_dict()
    result = BotEligibilityResult(
        ok=True,
        query=query,
        username=username_at,
        eligibility="eligible",
        message_fa=_MSG_ELIGIBLE,
        hard_block=False,
        verified=True,
        bot=bot_payload,
    )
    if use_cache:
        cache.set(_cache_key(username_at), _result_cache_payload(result), CACHE_TTL_SECONDS)
    return result


def _result_cache_payload(result: BotEligibilityResult) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "query": result.query,
        "username": result.username,
        "eligibility": result.eligibility,
        "message_fa": result.message_fa,
        "hard_block": result.hard_block,
        "verified": result.verified,
        "bot": result.bot,
        "api_code": result.api_code,
    }


def validate_bot_targets(
    bot_ids: list[str],
    *,
    strict: bool = False,
    peer_checks: dict[str, Any] | None = None,
) -> list[str]:
    """Return Persian error messages for bots that hard-block submission."""
    errors: list[str] = []
    seen: set[str] = set()
    checks = peer_checks or {}
    for raw in bot_ids:
        at, _ = parse_bot_peer_input(raw)
        if not at or at.casefold() in seen:
            continue
        seen.add(at.casefold())
        saved = checks.get(at) or checks.get(at.lstrip("@"))
        if isinstance(saved, dict) and saved.get("hard_block") and saved.get("verified"):
            label = (saved.get("bot") or {}).get("title") or at
            errors.append(f"{label}: {saved.get('message_fa') or _MSG_INSUFFICIENT}")
            continue
        if strict:
            result = check_bot_eligibility(at, use_cache=True)
            if result.hard_block:
                label = result.bot.get("title") or at
                errors.append(f"{label}: {result.message_fa}")
    return errors
