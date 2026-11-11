from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from apps.finance.models import ExchangeRate
from apps.finance.services import resolve_irr_per_ton


def irr_per_ton_from_exchange_id(exchange_rate_id) -> int | None:
    if not exchange_rate_id:
        return None
    try:
        row = ExchangeRate.objects.get(pk=exchange_rate_id)
    except ExchangeRate.DoesNotExist:
        return None
    details = row.details if isinstance(row.details, dict) else {}
    if details.get("irr_per_ton"):
        return int(details["irr_per_ton"])
    if row.ton_per_irr and row.ton_per_irr > 0:
        return int((Decimal(1) / row.ton_per_irr).to_integral_value(rounding=ROUND_HALF_UP))
    return None


def resolve_ton_display_rate(
    *,
    exchange_rate_id=None,
    rate_irr: int | None = None,
) -> tuple[int | None, str]:
    if rate_irr is not None and int(rate_irr) > 0:
        return int(rate_irr), "نرخ این برآورد"
    locked = irr_per_ton_from_exchange_id(exchange_rate_id)
    if locked and locked > 0:
        return locked, "نرخ زمان ثبت سفارش"
    market = resolve_irr_per_ton()
    if market > 0:
        return market, "برآورد با نرخ فعلی بازار"
    return None, ""


def ton_amount_to_irr(ton, irr_per_ton: int) -> int | None:
    if ton is None or ton == "" or irr_per_ton <= 0:
        return None
    try:
        amount = Decimal(str(ton))
    except Exception:
        return None
    if amount < 0:
        return None
    irr = (amount * Decimal(irr_per_ton)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return int(irr)
