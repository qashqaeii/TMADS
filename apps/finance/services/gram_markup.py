"""Silent customer markup on Nobitex Gram rates (admin-configured, default 0%)."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings


def active_gram_markup_percent() -> int:
    from apps.finance.models import GramRateMarkupRule

    rule = GramRateMarkupRule.objects.filter(is_active=True).order_by("-created_at").first()
    if rule is not None:
        return max(0, min(100, int(rule.percent)))
    return max(0, min(100, int(getattr(settings, "GRAM_RATE_MARKUP_PERCENT", 0) or 0)))


def gram_markup_factor(percent: int | None = None) -> Decimal:
    value = active_gram_markup_percent() if percent is None else max(0, min(100, int(percent)))
    return Decimal(1) + (Decimal(value) / Decimal(100))


def apply_gram_markup_amount(amount: Decimal | None, *, percent: int | None = None) -> Decimal | None:
    if amount is None:
        return None
    if not isinstance(amount, Decimal):
        amount = Decimal(str(amount))
    if not amount.is_finite() or amount <= 0:
        return amount
    factor = gram_markup_factor(percent)
    if factor == 1:
        return amount
    return amount * factor


def snapshot_with_customer_markup(snapshot):
    """Return a nobitex snapshot with markup applied; manual rates stay unchanged."""
    if snapshot is None:
        return None
    source = str(getattr(snapshot, "source", "") or "")
    if source == "manual":
        return snapshot
    percent = active_gram_markup_percent()
    if percent <= 0:
        return snapshot
    from apps.finance.services.ton_exchange_rate import TonRateSnapshot

    return TonRateSnapshot(
        source=snapshot.source,
        market_symbol=snapshot.market_symbol,
        stats_pair=snapshot.stats_pair,
        best_ask_irr=apply_gram_markup_amount(snapshot.best_ask_irr, percent=percent),
        best_bid_irr=apply_gram_markup_amount(snapshot.best_bid_irr, percent=percent),
        last_trade_irr=apply_gram_markup_amount(snapshot.last_trade_irr, percent=percent),
        fetched_at=snapshot.fetched_at,
        provider_timestamp_ms=snapshot.provider_timestamp_ms,
        fetch_status=snapshot.fetch_status,
        is_fresh=snapshot.is_fresh,
        exchange_rate_id=snapshot.exchange_rate_id,
    )
