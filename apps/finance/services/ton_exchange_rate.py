from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from decimal import ROUND_CEILING, Decimal
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from apps.finance.exceptions import (
    InsufficientLiquidityError,
    InvalidRateError,
    NobitexAPIError,
    StaleRateError,
)
from apps.finance.models import ExchangeRate
from apps.finance.services.nobitex_client import CACHE_KEY_RATE, NobitexClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TonRateSnapshot:
    source: str
    market_symbol: str
    stats_pair: str
    best_ask_irr: Decimal
    best_bid_irr: Decimal | None
    last_trade_irr: Decimal | None
    fetched_at: datetime
    provider_timestamp_ms: int | None
    fetch_status: str
    is_fresh: bool
    exchange_rate_id: str | None = None

    @property
    def irr_per_ton(self) -> int:
        return int(self.best_ask_irr.to_integral_value(rounding=ROUND_CEILING))


def compute_vwap_ask_cost(asks: list[tuple[Decimal, Decimal]], ton_amount: Decimal) -> tuple[Decimal, Decimal]:
    """Return (total_irr_cost, effective_irr_per_ton) for buying ton_amount from ask book."""
    if ton_amount <= 0:
        raise InvalidRateError("ton_amount_zero")
    remaining = ton_amount
    total_cost = Decimal("0")
    filled = Decimal("0")
    for price, qty in asks:
        take = min(remaining, qty)
        if take <= 0:
            continue
        total_cost += take * price
        filled += take
        remaining -= take
        if remaining <= 0:
            break
    if remaining > 0:
        raise InsufficientLiquidityError(
            f"insufficient_depth need={ton_amount} filled={filled}"
        )
    effective = total_cost / filled
    return total_cost, effective


def fetch_live_snapshot(*, persist: bool = True) -> TonRateSnapshot:
    client = NobitexClient()
    now = timezone.now()
    stats = client.fetch_market_stats()
    book = client.fetch_orderbook()
    best_ask = stats["best_ask_irr"]
    best_bid = stats.get("best_bid_irr")
    last_trade = book.get("last_trade_irr") or stats.get("last_trade_irr")
    snapshot = TonRateSnapshot(
        source="nobitex",
        market_symbol=book["market_symbol"],
        stats_pair=stats["stats_pair"],
        best_ask_irr=best_ask,
        best_bid_irr=best_bid,
        last_trade_irr=last_trade,
        fetched_at=now,
        provider_timestamp_ms=book.get("last_update_ms"),
        fetch_status="ok",
        is_fresh=True,
    )
    payload = {
        "irr_per_ton": snapshot.irr_per_ton,
        "best_ask_irr": str(best_ask),
        "best_bid_irr": str(best_bid) if best_bid else None,
        "last_trade_irr": str(last_trade) if last_trade else None,
        "market_symbol": snapshot.market_symbol,
        "stats_pair": snapshot.stats_pair,
        "fetched_at": now.isoformat(),
        "provider_timestamp_ms": book.get("last_update_ms"),
        "asks_depth_levels": len(book["asks"]),
        "market_closed": stats.get("is_closed", False),
        "fetch_status": "ok",
        "is_fresh": True,
        "vwap_reference": None,
    }
    cache.set(CACHE_KEY_RATE, {**payload, "source": "nobitex"}, timeout=settings.NOBITEX_CACHE_TTL_SECONDS)
    if persist:
        ExchangeRate.objects.filter(is_active=True, source="nobitex").update(is_active=False)
        ton_per_irr = (Decimal(1) / best_ask) if best_ask else Decimal(0)
        row = ExchangeRate.objects.create(
            ton_per_irr=ton_per_irr,
            source="nobitex",
            is_active=True,
            details={**payload, "exchange_rate_id": None},
        )
        payload["exchange_rate_id"] = str(row.id)
        row.details = payload
        row.save(update_fields=["details", "updated_at"])
        return TonRateSnapshot(
            source=snapshot.source,
            market_symbol=snapshot.market_symbol,
            stats_pair=snapshot.stats_pair,
            best_ask_irr=snapshot.best_ask_irr,
            best_bid_irr=snapshot.best_bid_irr,
            last_trade_irr=snapshot.last_trade_irr,
            fetched_at=snapshot.fetched_at,
            provider_timestamp_ms=snapshot.provider_timestamp_ms,
            fetch_status=snapshot.fetch_status,
            is_fresh=snapshot.is_fresh,
            exchange_rate_id=str(row.id),
        )
    return snapshot


def get_cached_snapshot(
    *,
    allow_stale: bool = False,
    allow_stale_display: bool | None = None,
) -> TonRateSnapshot | None:
    stale = allow_stale_display if allow_stale_display is not None else allow_stale
    cached = cache.get(CACHE_KEY_RATE)
    if cached:
        return _snapshot_from_details(cached, allow_stale=stale)
    row = ExchangeRate.objects.filter(is_active=True, source="nobitex").order_by("-created_at").first()
    if row and isinstance(row.details, dict):
        return _snapshot_from_details(row.details, allow_stale=stale, rate_id=str(row.id))
    return None


def resolve_manual_snapshot() -> TonRateSnapshot | None:
    row = ExchangeRate.objects.filter(is_active=True, source="manual").order_by("-created_at").first()
    if not row or not isinstance(row.details, dict):
        return None
    exp = row.details.get("manual_expires_at")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            if timezone.is_naive(exp_dt):
                exp_dt = timezone.make_aware(exp_dt, dt_timezone.utc)
            if exp_dt < timezone.now():
                return None
        except (TypeError, ValueError):
            pass
    snap = _snapshot_from_details(row.details, allow_stale=True, rate_id=str(row.id))
    if snap:
        return TonRateSnapshot(
            source="manual",
            market_symbol=snap.market_symbol,
            stats_pair=snap.stats_pair,
            best_ask_irr=snap.best_ask_irr,
            best_bid_irr=snap.best_bid_irr,
            last_trade_irr=snap.last_trade_irr,
            fetched_at=snap.fetched_at,
            provider_timestamp_ms=snap.provider_timestamp_ms,
            fetch_status="manual",
            is_fresh=True,
            exchange_rate_id=str(row.id),
        )
    return None


def get_pricing_snapshot(*, require_fresh: bool = True) -> TonRateSnapshot:
    manual = resolve_manual_snapshot()
    if manual:
        return manual
    snap = get_cached_snapshot(allow_stale=not require_fresh)
    if not snap:
        row = ExchangeRate.objects.filter(is_active=True, source="nobitex").order_by("-created_at").first()
        if row and isinstance(row.details, dict) and row.details.get("irr_per_ton"):
            snap = _snapshot_from_details(row.details, allow_stale=not require_fresh, rate_id=str(row.id))
    if not snap:
        return fetch_live_snapshot(persist=True)
    age = (timezone.now() - snap.fetched_at).total_seconds()
    if require_fresh and age > settings.NOBITEX_MAX_RATE_AGE_SECONDS:
        return fetch_live_snapshot(persist=True)
    return snap


def _snapshot_from_details(
    details: dict,
    *,
    allow_stale: bool = False,
    rate_id: str | None = None,
) -> TonRateSnapshot | None:
    try:
        fetched_raw = details.get("fetched_at")
        if fetched_raw:
            fetched_at = datetime.fromisoformat(fetched_raw.replace("Z", "+00:00"))
            if timezone.is_naive(fetched_at):
                fetched_at = timezone.make_aware(fetched_at, dt_timezone.utc)
        else:
            fetched_at = timezone.now()
        best_ask = Decimal(str(details["best_ask_irr"] if "best_ask_irr" in details else details["irr_per_ton"]))
        best_bid = Decimal(str(details["best_bid_irr"])) if details.get("best_bid_irr") else None
        last_trade = Decimal(str(details["last_trade_irr"])) if details.get("last_trade_irr") else None
        age = (timezone.now() - fetched_at).total_seconds()
        is_fresh = age <= settings.NOBITEX_MAX_RATE_AGE_SECONDS
        if not allow_stale and not is_fresh and details.get("source") == "nobitex":
            return None
        return TonRateSnapshot(
            source=details.get("source", "nobitex"),
            market_symbol=details.get("market_symbol", settings.NOBITEX_ORDERBOOK_SYMBOL),
            stats_pair=details.get("stats_pair", settings.NOBITEX_STATS_PAIR),
            best_ask_irr=best_ask,
            best_bid_irr=best_bid,
            last_trade_irr=last_trade,
            fetched_at=fetched_at,
            provider_timestamp_ms=details.get("provider_timestamp_ms"),
            fetch_status=details.get("fetch_status", "ok"),
            is_fresh=is_fresh,
            exchange_rate_id=rate_id or details.get("exchange_rate_id"),
        )
    except Exception:
        return None


def effective_rate_for_ton(ton_amount: Decimal, *, snapshot: TonRateSnapshot | None = None) -> dict[str, Any]:
    """VWAP when order book available; else best ask."""
    snap = snapshot or get_pricing_snapshot(require_fresh=True)
    client = NobitexClient()
    try:
        book = client.fetch_orderbook()
        cost, eff = compute_vwap_ask_cost(book["asks"], ton_amount)
        return {
            "rate_type": "vwap",
            "effective_rate_irr": eff,
            "total_irr_for_ton": cost,
            "base_rate_irr": snap.best_ask_irr,
            "snapshot": snap,
        }
    except (InsufficientLiquidityError, NobitexAPIError, InvalidRateError):
        eff = snap.best_ask_irr
        return {
            "rate_type": "best_ask",
            "effective_rate_irr": eff,
            "total_irr_for_ton": (ton_amount * eff),
            "base_rate_irr": snap.best_ask_irr,
            "snapshot": snap,
            "liquidity_limited": True,
        }
