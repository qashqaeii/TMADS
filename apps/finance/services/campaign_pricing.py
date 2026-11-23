from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN

from django.conf import settings
from django.utils import timezone

from apps.finance.exceptions import InsufficientLiquidityError, PricingError, StaleRateError
from apps.finance.services.money import ceil_irr
from apps.finance.services.ton_exchange_rate import (
    TonRateSnapshot,
    effective_rate_for_ton,
    get_pricing_snapshot,
    resolve_manual_snapshot,
)


def ton_from_advertising_budget(advertising_budget_irr: int, rate_irr: Decimal) -> Decimal:
    if advertising_budget_irr <= 0 or rate_irr <= 0:
        return Decimal("0")
    return (Decimal(advertising_budget_irr) / rate_irr).quantize(Decimal("0.000000001"))


def build_campaign_quote(advertising_budget_irr: int) -> dict:
    """
    Build locked quote payload for wizard / order creation.
    advertising_budget_irr: IRR reserved for Telegram ad spend (Gram/TON).
    """
    if advertising_budget_irr <= 0:
        raise PricingError("بودجه تبلیغ نامعتبر است.")

    from apps.finance.services.gram_markup import apply_gram_markup_amount, gram_markup_factor

    manual = resolve_manual_snapshot()
    raw_snapshot = manual or get_pricing_snapshot(require_fresh=True)
    # Silent admin markup applies only to market (Nobitex) rates, not manual overrides.
    markup_factor = Decimal("1") if manual else gram_markup_factor()
    snapshot = raw_snapshot
    base_rate = snapshot.best_ask_irr * markup_factor
    if not base_rate.is_finite() or base_rate <= 0:
        raise PricingError("نرخ معتبر در دسترس نیست.")
    # Match the documented TON budget precision before locking the purchase.
    est_ton = (Decimal(advertising_budget_irr) / base_rate).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    if est_ton <= 0:
        raise PricingError("محاسبه TON نامعتبر است.")

    rate_info = (
        {"rate_type": "manual", "effective_rate_irr": base_rate}
        if manual else effective_rate_for_ton(est_ton, snapshot=raw_snapshot)
    )
    effective_rate = rate_info["effective_rate_irr"]
    if not manual:
        effective_rate = apply_gram_markup_amount(effective_rate) or effective_rate
    if rate_info.get("liquidity_limited"):
        raise InsufficientLiquidityError("عمق بازار یا نرخ قطعی در دسترس نیست؛ دوباره تلاش کنید.")
    if rate_info["rate_type"] == "vwap" and rate_info.get("total_irr_for_ton"):
        market_cost = rate_info["total_irr_for_ton"]
        if not manual:
            market_cost = apply_gram_markup_amount(market_cost) or market_cost
        advertising_cost = ceil_irr(market_cost)
    else:
        advertising_cost = ceil_irr(est_ton * effective_rate)

    if advertising_cost > advertising_budget_irr:
        raise InsufficientLiquidityError("عمق بازار برای این بودجه کافی نیست.")

    # Prefer DB fee rule when active; fall back to settings for fresh quotes only.
    from apps.finance.models import PlatformFeeRule

    fee_rule = PlatformFeeRule.objects.filter(is_active=True).order_by("-created_at").first()
    fee_percent = int(fee_rule.percent) if fee_rule else int(settings.PLATFORM_SERVICE_FEE_PERCENT)
    buffer_percent = settings.TON_PRICING_RISK_BUFFER_PERCENT
    service_fee = advertising_cost * fee_percent // 100
    risk_buffer = advertising_cost * buffer_percent // 100
    total = advertising_cost + service_fee + risk_buffer

    ton_allocation = est_ton

    expires_at = timezone.now() + timedelta(seconds=settings.QUOTE_VALIDITY_SECONDS)

    return {
        "advertising_budget_irr": advertising_cost,
        "service_fee_irr": int(service_fee),
        "risk_buffer_irr": int(risk_buffer),
        "total_irr": int(total),
        "fee_percent": fee_percent,
        "risk_buffer_percent": buffer_percent,
        "irr_per_ton": int(effective_rate.to_integral_value(rounding=ROUND_CEILING)),
        "base_rate_irr": str(base_rate),
        "effective_rate_irr": str(effective_rate),
        "rate_type": rate_info["rate_type"],
        "ton_allocation": str(ton_allocation),
        "source": snapshot.source,
        "market_symbol": snapshot.market_symbol,
        "stats_pair": snapshot.stats_pair,
        "quote_status": "locked",
        "expires_at": expires_at.isoformat(),
        "provider_timestamp_ms": snapshot.provider_timestamp_ms,
        "snapshot_fetched_at": snapshot.fetched_at.isoformat(),
        "exchange_rate_id": snapshot.exchange_rate_id,
        "is_fresh": snapshot.is_fresh,
    }


def quote_expired(payload: dict) -> bool:
    raw = payload.get("expires_at")
    if not raw:
        return True
    try:
        from datetime import datetime

        exp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if timezone.is_naive(exp):
            exp = timezone.make_aware(exp)
        return exp < timezone.now()
    except (TypeError, ValueError):
        return True
