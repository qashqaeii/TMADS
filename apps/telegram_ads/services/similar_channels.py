"""Similar Channels: official getSimilarChannels when available, else cotarget fallback."""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from django.conf import settings
from django.core.cache import cache

from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.targeting.normalize import parse_bot_peer_input

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30 * 60
DEFAULT_LIMIT = 12
MAX_LIMIT = 24
MAX_VERIFY = 28
MIN_COTARGET_CUSTOMERS = 2


@dataclass
class SimilarChannelItem:
    username: str
    title: str
    photo_url: str = ""
    channel_id: int | None = None
    subscribers: int | None = None
    score: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "username": self.username,
            "title": self.title,
            "photo_url": self.photo_url,
            "score": self.score,
            "reasons": list(self.reasons),
        }
        if isinstance(self.channel_id, int) and self.channel_id != 0:
            payload["channel_id"] = self.channel_id
        if isinstance(self.subscribers, int) and self.subscribers > 0:
            payload["subscribers"] = self.subscribers
        return payload


@dataclass
class SimilarChannelsResult:
    ok: bool
    seed: str | None
    items: list[SimilarChannelItem] = field(default_factory=list)
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


def similar_channels_enabled() -> bool:
    return bool(getattr(settings, "SIMILAR_CHANNELS_ENABLED", True))


def _normalize_username(value: str) -> str | None:
    at, _ = parse_bot_peer_input(value)
    return at


def _username_key(username: str) -> str:
    return username.casefold().lstrip("@")


def _strip_html(value: str, *, max_len: int = 200) -> str:
    text = re.sub(r"<[^>]*>", "", str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def _safe_https_photo(url: str | None) -> str:
    value = str(url or "").strip()
    if re.fullmatch(r"https://[^\s<>\"']+", value, flags=re.IGNORECASE):
        return value[:500]
    # common CDN form from ads UI HTML snippets
    m = re.search(r'src="(https://cdn\d*\.telesco\.pe/file/[^"]+)"', value)
    if m:
        return m.group(1)[:500]
    return ""


def _account_scope_for_customer(customer) -> str:
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
        logger.exception("similar channels: account scope resolve failed")
    return f"customer:{getattr(customer, 'pk', 'x')}:{token_scope}"


def _cache_key(seed: str, *, account_scope: str, exclude_keys: tuple[str, ...], limit: int) -> str:
    excl = ",".join(exclude_keys[:100])
    digest = hashlib.sha256(f"{seed}|{excl}|{limit}".encode()).hexdigest()[:24]
    return f"tmads:similar_channels:v1:{account_scope}:{digest}"


def _is_resolved_channel_id(value: Any) -> bool:
    # شناسه کانال تلگرام معمولاً منفی است (مثلاً -100…)؛ صفر نامعتبر است.
    return isinstance(value, int) and value != 0


def _sanitize_exclude(raw: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        at = _normalize_username(str(item))
        if not at:
            continue
        key = _username_key(at)
        if key in seen:
            continue
        seen.add(key)
        out.append(at)
        if len(out) >= 100:
            break
    return out


def _parse_api_rows(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, dict):
        for key in ("channels", "items", "result", "similar"):
            if isinstance(raw.get(key), list):
                return [x for x in raw[key] if isinstance(x, dict)]
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


def _row_username(row: dict[str, Any]) -> str | None:
    # `name` در پاسخ ads.telegram عنوان نمایشی است، نه یوزرنیم.
    for key in ("username", "channel_username"):
        at = _normalize_username(str(row.get(key) or ""))
        if at:
            return at
    return None


def _row_subscribers(row: dict[str, Any]) -> int | None:
    for key in ("subscribers", "members_count", "members"):
        value = row.get(key)
        if isinstance(value, int) and value > 0:
            return value
        if isinstance(value, str) and value.replace(",", "").isdigit():
            return int(value.replace(",", ""))
    blob = str(row.get("cb_item") or row.get("desc") or "")
    match = re.search(r"([\d,]+)\s*subscribers", blob, flags=re.IGNORECASE)
    if match:
        try:
            return int(match.group(1).replace(",", ""))
        except ValueError:
            return None
    return None


def _cotarget_candidates(seed_key: str, *, limit: int = 40) -> list[tuple[str, int]]:
    if not seed_key:
        return []
    try:
        from apps.campaigns.models import Campaign

        rows = (
            Campaign.objects.filter(target_type="channels")
            .exclude(status=Campaign.Status.CANCELLED)
            .values_list("customer_id", "targeting__config")[:2500]
        )
    except Exception:
        logger.exception("similar channels: cotarget load failed")
        return []

    partners: dict[str, set[str]] = {}
    for customer_id, cfg in rows:
        if not isinstance(cfg, dict):
            continue
        channels: list[str] = []
        for raw in cfg.get("channel_ids") or []:
            at = _normalize_username(str(raw))
            if at:
                channels.append(_username_key(at))
        if seed_key not in channels:
            continue
        cust = str(customer_id)
        for key in channels:
            if key == seed_key:
                continue
            partners.setdefault(key, set()).add(cust)

    ranked = sorted(
        (
            (key, len(customers))
            for key, customers in partners.items()
            if len(customers) >= MIN_COTARGET_CUSTOMERS
        ),
        key=lambda item: (-item[1], item[0]),
    )
    return ranked[:limit]


class SimilarChannelsService:
    def get_similar(
        self,
        seed: str,
        *,
        customer=None,
        exclude: list[str] | None = None,
        limit: int = DEFAULT_LIMIT,
        use_cache: bool = True,
    ) -> SimilarChannelsResult:
        if not similar_channels_enabled():
            return SimilarChannelsResult(
                ok=True,
                seed=None,
                items=[],
                message_fa="پیشنهاد کانال‌های مشابه فعلاً غیرفعال است.",
                reason="feature_disabled",
                feature_enabled=False,
            )

        seed_at = _normalize_username(seed)
        if not seed_at:
            return SimilarChannelsResult(
                ok=False,
                seed=None,
                message_fa="برای پیشنهاد مشابه، یک کانال معتبر انتخاب کنید.",
                reason="invalid_seed",
            )

        limit = max(1, min(int(limit or DEFAULT_LIMIT), MAX_LIMIT))
        exclude_list = _sanitize_exclude(exclude)
        exclude_keys = tuple(_username_key(x) for x in exclude_list)
        account_scope = _account_scope_for_customer(customer)
        cache_key = _cache_key(seed_at, account_scope=account_scope, exclude_keys=exclude_keys, limit=limit)

        if use_cache:
            cached = cache.get(cache_key)
            if isinstance(cached, dict) and cached.get("ok") is not None:
                return SimilarChannelsResult(
                    ok=bool(cached.get("ok")),
                    seed=cached.get("seed"),
                    items=[SimilarChannelItem(**item) for item in cached.get("items") or [] if isinstance(item, dict)],
                    message_fa=str(cached.get("message_fa") or ""),
                    reason=str(cached.get("reason") or ""),
                    feature_enabled=True,
                )

        from apps.telegram_ads.client import TelegramAdsClient

        client = TelegramAdsClient()
        try:
            seed_info = client.resolve_target_channel(seed_at)
        except TelegramAdsError:
            logger.exception("similar channels: seed resolve failed for %s", seed_at)
            return SimilarChannelsResult(
                ok=False,
                seed=seed_at,
                message_fa="بررسی کانال مبدأ فعلاً ممکن نیست.",
                reason="seed_unresolved",
            )

        if not _is_resolved_channel_id(seed_info.get("channel_id")):
            return SimilarChannelsResult(
                ok=False,
                seed=seed_at,
                message_fa="کانال مبدأ برای هدف‌گیری تأیید نشد.",
                reason="seed_unresolved",
            )

        blocked = {_username_key(seed_at), *exclude_keys}
        raw_candidates: list[dict[str, Any]] = []

        # 1) Official promote API when the method exists for this account.
        try:
            api_raw = client.get_similar_channels(
                channels=[seed_info.get("username") or seed_at.lstrip("@"), seed_info["channel_id"]],
                for_target="channels",
            )
            for row in _parse_api_rows(api_raw):
                username = _row_username(row)
                if not username or _username_key(username) in blocked:
                    continue
                raw_candidates.append(
                    {
                        "username": username,
                        "title": _strip_html(str(row.get("title") or row.get("name") or username)),
                        "photo_url": _safe_https_photo(row.get("photo_url") or row.get("photo")),
                        "subscribers": _row_subscribers(row),
                        "score": 100,
                        "reasons": ["api"],
                    }
                )
        except TelegramAdsError:
            logger.info("similar channels: getSimilarChannels unavailable for seed=%s", seed_at)

        # 2) Cotarget fallback from historical channel targeting.
        if len(raw_candidates) < limit:
            have = {_username_key(c["username"]) for c in raw_candidates}
            for key, weight in _cotarget_candidates(_username_key(seed_at)):
                if key in blocked or key in have:
                    continue
                raw_candidates.append(
                    {
                        "username": f"@{key}",
                        "title": f"@{key}",
                        "photo_url": "",
                        "subscribers": None,
                        "score": 40 + min(weight, 20),
                        "reasons": ["cotarget"],
                    }
                )
                have.add(key)
                if len(raw_candidates) >= MAX_VERIFY:
                    break

        items: list[SimilarChannelItem] = []
        for cand in raw_candidates:
            if len(items) >= limit:
                break
            at = _normalize_username(cand["username"])
            if not at or _username_key(at) in blocked:
                continue
            try:
                resolved = client.resolve_target_channel(at)
            except TelegramAdsError:
                continue
            if not _is_resolved_channel_id(resolved.get("channel_id")):
                continue
            username = _normalize_username(str(resolved.get("username") or at)) or at
            if _username_key(username) in blocked:
                continue
            title = _strip_html(str(resolved.get("title") or cand.get("title") or username))
            photo = _safe_https_photo(resolved.get("photo_url")) or cand.get("photo_url") or ""
            subs = cand.get("subscribers")
            if not isinstance(subs, int) or subs <= 0:
                subs = None
            items.append(
                SimilarChannelItem(
                    username=username,
                    title=title,
                    photo_url=photo,
                    channel_id=resolved["channel_id"],
                    subscribers=subs,
                    score=int(cand.get("score") or 0),
                    reasons=list(cand.get("reasons") or []),
                )
            )
            blocked.add(_username_key(username))

        message = (
            f"{len(items)} کانال مشابه پیدا شد."
            if items
            else "کانال مشابهی پیدا نشد؛ کانال دیگری را امتحان کنید."
        )
        result = SimilarChannelsResult(
            ok=True,
            seed=seed_at,
            items=items,
            message_fa=message,
            reason="ok" if items else "empty",
        )
        if use_cache:
            cache.set(
                cache_key,
                {
                    "ok": result.ok,
                    "seed": result.seed,
                    "items": [
                        {
                            "username": i.username,
                            "title": i.title,
                            "photo_url": i.photo_url,
                            "channel_id": i.channel_id,
                            "subscribers": i.subscribers,
                            "score": i.score,
                            "reasons": i.reasons,
                        }
                        for i in result.items
                    ],
                    "message_fa": result.message_fa,
                    "reason": result.reason,
                },
                CACHE_TTL_SECONDS,
            )
        return result
