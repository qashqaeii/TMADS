from __future__ import annotations

import logging
import time
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from django.conf import settings

from apps.finance.exceptions import InvalidRateError, NobitexAPIError

logger = logging.getLogger(__name__)

CACHE_KEY_RATE = "finance:ton_rate_snapshot"


def _d(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        d = Decimal(str(value))
        if d <= 0:
            return None
        return d
    except (InvalidOperation, ValueError):
        return None


class NobitexClient:
    """Read-only Nobitex public API client (no trading, no token)."""

    def __init__(
        self,
        *,
        timeout: float | None = None,
        retries: int | None = None,
        base_url: str | None = None,
    ):
        self.base_url = (base_url or settings.NOBITEX_API_BASE_URL).rstrip("/")
        self.timeout = timeout or settings.NOBITEX_HTTP_TIMEOUT_SECONDS
        self.retries = settings.NOBITEX_HTTP_RETRIES if retries is None else max(0, int(retries))
        self.stats_src = settings.NOBITEX_STATS_SRC_CURRENCY
        self.stats_dst = settings.NOBITEX_STATS_DST_CURRENCY
        self.stats_pair = settings.NOBITEX_STATS_PAIR
        self.orderbook_symbol = settings.NOBITEX_ORDERBOOK_SYMBOL

    def _get(self, path: str, *, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.get(url, params=params)
                if response.status_code == 429:
                    time.sleep(min(2 ** attempt, 4))
                    continue
                if response.status_code >= 500:
                    time.sleep(0.5)
                    continue
                data = response.json()
                if not isinstance(data, dict):
                    raise NobitexAPIError("invalid_json")
                if data.get("status") != "ok":
                    raise NobitexAPIError(
                        data.get("code") or data.get("message") or "api_failed"
                    )
                return data
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self.retries:
                    time.sleep(0.3)
        raise NobitexAPIError(str(last_exc or "request_failed"))

    def fetch_market_stats(self) -> dict[str, Any]:
        data = self._get(
            "/market/stats",
            params={"srcCurrency": self.stats_src, "dstCurrency": self.stats_dst},
        )
        stats = data.get("stats") or {}
        pair = stats.get(self.stats_pair)
        if not pair:
            raise NobitexAPIError(f"missing_pair:{self.stats_pair}")
        if pair.get("isClosed"):
            raise NobitexAPIError("market_closed")
        best_sell = _d(pair.get("bestSell"))
        best_buy = _d(pair.get("bestBuy"))
        latest = _d(pair.get("latest"))
        if not best_sell:
            raise InvalidRateError("missing_best_sell")
        return {
            "stats_pair": self.stats_pair,
            "is_closed": bool(pair.get("isClosed")),
            "best_ask_irr": best_sell,
            "best_bid_irr": best_buy,
            "last_trade_irr": latest,
            "mark_irr": _d(pair.get("mark")),
            "raw_stats": pair,
        }

    def fetch_orderbook(self) -> dict[str, Any]:
        data = self._get(f"/v3/orderbook/{self.orderbook_symbol}")
        last_trade = _d(data.get("lastTradePrice"))
        asks_raw = data.get("asks") or []
        bids_raw = data.get("bids") or []
        asks = []
        for row in asks_raw:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                price, qty = _d(row[0]), _d(row[1])
                if price and qty:
                    asks.append((price, qty))
        bids = []
        for row in bids_raw:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                price, qty = _d(row[0]), _d(row[1])
                if price and qty:
                    bids.append((price, qty))
        if not asks:
            raise InvalidRateError("empty_asks")
        return {
            "market_symbol": self.orderbook_symbol,
            "last_update_ms": data.get("lastUpdate"),
            "last_trade_irr": last_trade,
            "asks": asks,
            "bids": bids,
            "raw": {k: data[k] for k in ("status", "lastUpdate", "lastTradePrice") if k in data},
        }
