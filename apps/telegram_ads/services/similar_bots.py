"""Similar Bots orchestration: catalog recommendations + official getTargetBot gate."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.core.cache import cache

from apps.telegram_ads.services.bot_eligibility import check_bot_eligibility
from apps.telegram_ads.services.bot_recommendation import (
    BotRecommendationAdapter,
    CatalogBotRecommendationAdapter,
    RecommendationCandidate,
    normalize_catalog_username,
)
from apps.telegram_ads.targeting.normalize import parse_bot_peer_input

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30 * 60
DEFAULT_LIMIT = 12
MAX_LIMIT = 24
MAX_VERIFY_ATTEMPTS = 36


@dataclass
class SimilarBotItem:
    username: str
    title: str
    photo_url: str = ""
    bot_id: int | None = None
    monthly_users: int | None = None
    eligibility: str = "eligible"
    verified: bool = True
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "username": self.username,
            "title": self.title,
            "photo_url": self.photo_url,
            "eligibility": self.eligibility,
            "verified": self.verified,
            "score": self.score,
            "reasons": list(self.reasons),
        }
        if isinstance(self.bot_id, int) and self.bot_id > 0:
            payload["bot_id"] = self.bot_id
        if isinstance(self.monthly_users, int) and self.monthly_users > 0:
            payload["monthly_users"] = self.monthly_users
        return payload


@dataclass
class SimilarBotsResult:
    ok: bool
    seed: str | None
    items: list[SimilarBotItem] = field(default_factory=list)
    message_fa: str = ""
    reason: str = ""
    feature_enabled: bool = True

    def to_json(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "seed": self.seed,
            "items": [item.to_json() for item in self.items],
            "message_fa": self.message_fa,
            "reason": self.reason,
            "feature_enabled": self.feature_enabled,
        }


def similar_bots_enabled() -> bool:
    return bool(getattr(settings, "SIMILAR_BOTS_ENABLED", True))


def _account_scope_for_customer(customer) -> str:
    """Scope caches to the customer's provisioned ads account when available."""
    token_scope = hashlib.sha256(settings.TELEGRAM_ADS_API_TOKEN.encode()).hexdigest()[:16]
    if customer is None:
        return f"central:{token_scope}"
    try:
        from apps.telegram_ads.models import RelatedAccountRequest

        row = (
            RelatedAccountRequest.objects.filter(customer=customer, status="provisioned")
            .exclude(remote_account_id="")
            .only("remote_account_id")
            .first()
        )
        if row and row.remote_account_id:
            return f"child:{row.remote_account_id}:{token_scope}"
    except Exception:
        logger.exception("similar bots: account scope resolve failed")
    return f"customer:{customer.pk}:{token_scope}"


def _cache_key(seed: str, *, account_scope: str, exclude_keys: tuple[str, ...], limit: int) -> str:
    excl = ",".join(exclude_keys[:100])
    digest = hashlib.sha256(f"{seed}|{excl}|{limit}".encode()).hexdigest()[:24]
    return f"tmads:similar_bots:v1:{account_scope}:{digest}"


def _sanitize_exclude(raw: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        at = normalize_catalog_username(str(item))
        if not at:
            continue
        key = at.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(at)
        if len(out) >= 100:
            break
    return out


def _safe_https_photo(url: str | None) -> str:
    value = str(url or "").strip()
    if re.fullmatch(r"https://[^\s<>\"']+", value, flags=re.IGNORECASE):
        return value[:500]
    return ""


def _title_from_eligibility(cand: RecommendationCandidate, bot: dict[str, Any]) -> str:
    title = str(bot.get("title") or "").strip()
    if title:
        title = re.sub(r"<[^>]*>", "", title)
        title = re.sub(r"\s+", " ", title).strip()[:200]
        if title:
            return title
    return cand.title or cand.username


class SimilarBotsService:
    def __init__(self, adapter: BotRecommendationAdapter | None = None):
        self.adapter = adapter or CatalogBotRecommendationAdapter()

    def get_similar(
        self,
        seed: str,
        *,
        customer=None,
        exclude: list[str] | None = None,
        limit: int = DEFAULT_LIMIT,
        use_cache: bool = True,
    ) -> SimilarBotsResult:
        if not similar_bots_enabled():
            return SimilarBotsResult(
                ok=True,
                seed=None,
                items=[],
                message_fa="پیشنهاد ربات‌های مشابه فعلاً غیرفعال است.",
                reason="feature_disabled",
                feature_enabled=False,
            )

        seed_at, _ = parse_bot_peer_input(seed)
        if not seed_at:
            return SimilarBotsResult(
                ok=False,
                seed=None,
                items=[],
                message_fa="نام کاربری ربات معتبر نیست.",
                reason="invalid_seed",
            )

        limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
        exclude_list = _sanitize_exclude(exclude)
        # Seed itself must never appear in suggestions.
        if seed_at.casefold() not in {x.casefold() for x in exclude_list}:
            exclude_list = [seed_at, *exclude_list]

        account_scope = _account_scope_for_customer(customer)
        exclude_keys = tuple(sorted(x.casefold() for x in exclude_list))
        cache_key = _cache_key(seed_at.casefold(), account_scope=account_scope, exclude_keys=exclude_keys, limit=limit)

        if use_cache:
            cached = cache.get(cache_key)
            if isinstance(cached, dict) and cached.get("ok") is True:
                items = []
                for row in cached.get("items") or []:
                    if not isinstance(row, dict):
                        continue
                    items.append(
                        SimilarBotItem(
                            username=str(row.get("username") or ""),
                            title=str(row.get("title") or ""),
                            photo_url=str(row.get("photo_url") or ""),
                            bot_id=row.get("bot_id") if isinstance(row.get("bot_id"), int) else None,
                            monthly_users=row.get("monthly_users") if isinstance(row.get("monthly_users"), int) else None,
                            eligibility=str(row.get("eligibility") or "eligible"),
                            verified=bool(row.get("verified")),
                            score=int(row.get("score") or 0),
                            reasons=list(row.get("reasons") or []),
                        )
                    )
                return SimilarBotsResult(
                    ok=True,
                    seed=seed_at,
                    items=[i for i in items if i.username],
                    message_fa=str(cached.get("message_fa") or ""),
                    reason=str(cached.get("reason") or "cache_hit"),
                )

        # Seed must itself be eligible before we recommend peers.
        seed_check = check_bot_eligibility(seed_at, use_cache=True, account_scope=account_scope)
        if seed_check.eligibility == "invalid_bot":
            return SimilarBotsResult(
                ok=False,
                seed=seed_at,
                items=[],
                message_fa=seed_check.message_fa,
                reason="invalid_seed",
            )
        if seed_check.eligibility == "insufficient_audience":
            return SimilarBotsResult(
                ok=True,
                seed=seed_at,
                items=[],
                message_fa="برای این ربات پیشنهاد معتبری در دسترس نیست.",
                reason="seed_blocked",
            )
        if seed_check.eligibility in {"api_unavailable", "unknown"} or not (
            seed_check.eligibility == "eligible" and seed_check.verified
        ):
            return SimilarBotsResult(
                ok=True,
                seed=seed_at,
                items=[],
                message_fa="فعلاً امکان پیشنهاد ربات‌های مشابه نیست؛ می‌توانید ربات را دستی اضافه کنید.",
                reason="seed_unverified",
            )

        customer_id = str(getattr(customer, "pk", "") or "") or None
        try:
            candidates = self.adapter.recommend(
                seed=seed_at,
                exclude={x.casefold() for x in exclude_list},
                customer_id=customer_id,
                limit=limit,
            )
        except Exception:
            logger.exception("similar bots adapter failed for seed=%s", seed_at)
            return SimilarBotsResult(
                ok=True,
                seed=seed_at,
                items=[],
                message_fa="پیشنهادها موقتاً در دسترس نیست؛ ساخت کمپین را می‌توانید ادامه دهید.",
                reason="adapter_error",
            )

        items = self._verify_candidates(candidates, limit=limit, account_scope=account_scope)
        reason = "ok" if items else "no_matches"
        message = "" if items else "ربات مشابه معتبری پیدا نشد."
        result = SimilarBotsResult(
            ok=True,
            seed=seed_at,
            items=items,
            message_fa=message,
            reason=reason,
        )
        if use_cache:
            cache.set(
                cache_key,
                {
                    "ok": True,
                    "items": [i.to_json() for i in items],
                    "message_fa": message,
                    "reason": reason,
                },
                CACHE_TTL_SECONDS,
            )
        return result

    def _verify_candidates(
        self,
        candidates: list[RecommendationCandidate],
        *,
        limit: int,
        account_scope: str,
    ) -> list[SimilarBotItem]:
        verified: list[SimilarBotItem] = []
        attempts = 0
        for cand in candidates:
            if len(verified) >= limit:
                break
            if attempts >= MAX_VERIFY_ATTEMPTS:
                break
            attempts += 1
            try:
                result = check_bot_eligibility(cand.username, use_cache=True, account_scope=account_scope)
            except Exception:
                logger.warning("similar bots eligibility failed for %s", cand.username)
                continue
            if not (result.eligibility == "eligible" and result.verified and result.ok):
                continue
            bot = result.bot if isinstance(result.bot, dict) else {}
            bot_id = bot.get("bot_id")
            if not isinstance(bot_id, int) or isinstance(bot_id, bool) or bot_id <= 0:
                continue
            username = result.username or cand.username
            photo = _safe_https_photo(bot.get("photo_url")) or cand.photo_url
            verified.append(
                SimilarBotItem(
                    username=username,
                    title=_title_from_eligibility(cand, bot),
                    photo_url=photo,
                    bot_id=bot_id,
                    monthly_users=cand.monthly_users,
                    eligibility="eligible",
                    verified=True,
                    score=cand.score,
                    reasons=list(cand.reasons),
                )
            )
        return verified
