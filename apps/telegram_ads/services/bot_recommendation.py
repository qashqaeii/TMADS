"""Bot recommendation adapters — catalog-first, no ads.telegram.org web session."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from django.db.models import Q

from apps.telegram_ads.models import TargetBotCatalogEntry
from apps.telegram_ads.targeting.normalize import parse_bot_peer_input

logger = logging.getLogger(__name__)

_HTTPS_PHOTO_RE = re.compile(r"^https://[^\s<>\"']+$", re.IGNORECASE)

# Minimum score to surface a candidate — avoids filler unrelated suggestions.
MIN_RECOMMENDATION_SCORE = 25
# Platform co-occurrence only when enough distinct customers share the pair.
MIN_COTARGET_CUSTOMERS = 3


@dataclass(frozen=True)
class RecommendationCandidate:
    username: str
    title: str = ""
    photo_url: str = ""
    monthly_users: int | None = None
    score: int = 0
    reasons: tuple[str, ...] = ()
    category: str = ""
    tags: tuple[str, ...] = ()
    language_codes: tuple[str, ...] = ()
    topic_ids: tuple[int, ...] = ()


@dataclass
class SeedContext:
    username: str
    category: str = ""
    tags: set[str] = field(default_factory=set)
    language_codes: set[str] = field(default_factory=set)
    topic_ids: set[int] = field(default_factory=set)
    related: set[str] = field(default_factory=set)


def normalize_catalog_username(value: str) -> str | None:
    at, _ = parse_bot_peer_input(value)
    if not at:
        return None
    return at


def _strip_unsafe_text(value: str, *, max_len: int = 200) -> str:
    text = re.sub(r"<[^>]*>", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _safe_photo_url(value: str) -> str:
    url = str(value or "").strip()
    if _HTTPS_PHOTO_RE.fullmatch(url):
        return url[:500]
    return ""


def _as_str_set(values: Any) -> set[str]:
    out: set[str] = set()
    if not isinstance(values, (list, tuple, set)):
        return out
    for item in values:
        text = str(item or "").strip().casefold()
        if text:
            out.add(text)
    return out


def _as_int_set(values: Any) -> set[int]:
    out: set[int] = set()
    if not isinstance(values, (list, tuple, set)):
        return out
    for item in values:
        if isinstance(item, bool):
            continue
        if isinstance(item, int) and item > 0:
            out.add(item)
        else:
            try:
                n = int(item)
            except (TypeError, ValueError):
                continue
            if n > 0:
                out.add(n)
    return out


def _username_key(username: str) -> str:
    return username.casefold().lstrip("@")


class BotRecommendationAdapter(Protocol):
    def recommend(
        self,
        *,
        seed: str,
        exclude: set[str],
        customer_id: str | None,
        limit: int,
    ) -> list[RecommendationCandidate]:
        ...


def load_seed_context(seed_username: str) -> SeedContext:
    at = normalize_catalog_username(seed_username)
    if not at:
        return SeedContext(username="")
    ctx = SeedContext(username=at)
    row = (
        TargetBotCatalogEntry.objects.filter(is_active=True)
        .filter(Q(username__iexact=at) | Q(username__iexact=at.lstrip("@")))
        .first()
    )
    if not row:
        return ctx
    related = set()
    for raw in row.related_usernames or []:
        n = normalize_catalog_username(str(raw))
        if n:
            related.add(_username_key(n))
    return SeedContext(
        username=at,
        category=(row.category or "").strip().casefold(),
        tags=_as_str_set(row.tags),
        language_codes=_as_str_set(row.language_codes),
        topic_ids=_as_int_set(row.topic_ids),
        related=related,
    )


def _customer_history_keys(customer_id: str | None) -> set[str]:
    if not customer_id:
        return set()
    try:
        from apps.campaigns.models import Campaign

        configs = (
            Campaign.objects.filter(customer_id=customer_id, target_type="bots")
            .exclude(status=Campaign.Status.CANCELLED)
            .values_list("targeting__config", flat=True)[:200]
        )
    except Exception:
        logger.exception("similar bots: customer history load failed")
        return set()
    keys: set[str] = set()
    for cfg in configs:
        if not isinstance(cfg, dict):
            continue
        for raw in cfg.get("bot_ids") or []:
            at = normalize_catalog_username(str(raw))
            if at:
                keys.add(_username_key(at))
    return keys


def _platform_cotarget_keys(seed_key: str) -> dict[str, int]:
    """Anonymized co-occurrence: only pairs seen across enough distinct customers."""
    if not seed_key:
        return {}
    try:
        from apps.campaigns.models import Campaign

        rows = (
            Campaign.objects.filter(target_type="bots")
            .exclude(status=Campaign.Status.CANCELLED)
            .values_list("customer_id", "targeting__config")[:2000]
        )
    except Exception:
        logger.exception("similar bots: cotarget aggregate failed")
        return {}

    # bot_key -> set of customer_ids that co-targeted with seed
    partners: dict[str, set[str]] = {}
    for customer_id, cfg in rows:
        if not isinstance(cfg, dict):
            continue
        bots = []
        for raw in cfg.get("bot_ids") or []:
            at = normalize_catalog_username(str(raw))
            if at:
                bots.append(_username_key(at))
        if seed_key not in bots:
            continue
        cust = str(customer_id)
        for key in bots:
            if key == seed_key:
                continue
            partners.setdefault(key, set()).add(cust)

    return {
        key: len(customers)
        for key, customers in partners.items()
        if len(customers) >= MIN_COTARGET_CUSTOMERS
    }


def score_catalog_entry(
    entry: TargetBotCatalogEntry,
    *,
    seed: SeedContext,
    customer_history: set[str],
    cotarget: dict[str, int],
) -> RecommendationCandidate | None:
    at = normalize_catalog_username(entry.username)
    if not at or not seed.username:
        return None
    if _username_key(at) == _username_key(seed.username):
        return None

    score = 0
    reasons: list[str] = []
    cand_key = _username_key(at)
    cand_related = {_username_key(u) for u in (normalize_catalog_username(str(x)) or "" for x in (entry.related_usernames or [])) if u}
    seed_key = _username_key(seed.username)

    if cand_key in seed.related or seed_key in cand_related:
        score += 100
        reasons.append("related")

    cand_category = (entry.category or "").strip().casefold()
    if seed.category and cand_category and seed.category == cand_category:
        score += 40
        reasons.append("category")

    shared_tags = seed.tags & _as_str_set(entry.tags)
    if shared_tags:
        score += 15 * min(len(shared_tags), 4)
        reasons.append("tags")

    shared_langs = seed.language_codes & _as_str_set(entry.language_codes)
    if shared_langs:
        score += 10 * min(len(shared_langs), 3)
        reasons.append("language")

    shared_topics = seed.topic_ids & _as_int_set(entry.topic_ids)
    if shared_topics:
        score += 10 * min(len(shared_topics), 3)
        reasons.append("topics")

    if cand_key in customer_history:
        score += 25
        reasons.append("customer_history")

    support = cotarget.get(cand_key, 0)
    if support:
        score += min(30, support * 5)
        reasons.append("cotarget")

    if entry.priority:
        score += max(-20, min(20, int(entry.priority)))

    if score < MIN_RECOMMENDATION_SCORE:
        return None

    monthly = entry.monthly_users
    if monthly is not None and (not isinstance(monthly, int) or isinstance(monthly, bool) or monthly <= 0):
        monthly = None

    return RecommendationCandidate(
        username=at,
        title=_strip_unsafe_text(entry.title or at),
        photo_url=_safe_photo_url(entry.photo_url),
        monthly_users=monthly,
        score=score,
        reasons=tuple(reasons),
        category=cand_category,
        tags=tuple(sorted(_as_str_set(entry.tags))),
        language_codes=tuple(sorted(_as_str_set(entry.language_codes))),
        topic_ids=tuple(sorted(_as_int_set(entry.topic_ids))),
    )


class CatalogBotRecommendationAdapter:
    """Primary recommendation source: curated catalog + privacy-safe signals."""

    def recommend(
        self,
        *,
        seed: str,
        exclude: set[str],
        customer_id: str | None,
        limit: int,
    ) -> list[RecommendationCandidate]:
        seed_ctx = load_seed_context(seed)
        if not seed_ctx.username:
            return []

        exclude_keys = {_username_key(x) for x in exclude if x}
        exclude_keys.add(_username_key(seed_ctx.username))

        customer_history = _customer_history_keys(customer_id)
        cotarget = _platform_cotarget_keys(_username_key(seed_ctx.username))

        # Pull a bounded candidate pool. Prefer same category / related when seed known.
        qs = TargetBotCatalogEntry.objects.filter(is_active=True)
        if seed_ctx.category:
            related_filter = Q(category__iexact=seed_ctx.category)
            for rel in list(seed_ctx.related)[:40]:
                related_filter |= Q(username__iexact=rel) | Q(username__iexact=f"@{rel}")
            # Also include bots that list the seed as related.
            related_filter |= Q(related_usernames__icontains=seed_ctx.username.lstrip("@"))
            pooled = list(qs.filter(related_filter).order_by("-priority")[:120])
            # If category pool is thin, widen to active catalog (still scored/thresholded).
            if len(pooled) < 12:
                seen = {e.pk for e in pooled}
                for extra in qs.order_by("-priority")[:80]:
                    if extra.pk not in seen:
                        pooled.append(extra)
        else:
            # Seed not in catalog: only explicit related reverse links + cotarget/history overlap.
            pooled = list(qs.filter(related_usernames__icontains=seed_ctx.username.lstrip("@")).order_by("-priority")[:80])
            history_or_co = customer_history | set(cotarget.keys())
            if history_or_co:
                for extra in qs.order_by("-priority")[:200]:
                    key = _username_key(normalize_catalog_username(extra.username) or "")
                    if key in history_or_co:
                        pooled.append(extra)

        scored: list[RecommendationCandidate] = []
        seen_keys: set[str] = set()
        for entry in pooled:
            cand = score_catalog_entry(
                entry,
                seed=seed_ctx,
                customer_history=customer_history,
                cotarget=cotarget,
            )
            if not cand:
                continue
            key = _username_key(cand.username)
            if key in exclude_keys or key in seen_keys:
                continue
            seen_keys.add(key)
            scored.append(cand)

        scored.sort(key=lambda c: (-c.score, c.username.casefold()))
        return scored[: max(1, min(limit * 3, 60))]
