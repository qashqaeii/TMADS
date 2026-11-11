from decimal import Decimal

from django import template

from apps.finance.services.ton_equiv import resolve_ton_display_rate, ton_amount_to_irr

register = template.Library()


def _ton_or_none(amount):
    if amount is None or amount == "":
        return None
    try:
        return Decimal(str(amount))
    except Exception:
        return None


@register.inclusion_tag("includes/ton_amount.html")
def ton_amount(amount, symbol="◈", exchange_rate_id=None, rate_irr=None):
    parsed = _ton_or_none(amount)
    has_value = parsed is not None
    irr_per_ton, rate_hint = resolve_ton_display_rate(
        exchange_rate_id=exchange_rate_id,
        rate_irr=rate_irr,
    )
    irr_total = ton_amount_to_irr(parsed, irr_per_ton) if has_value and irr_per_ton else None
    return {
        "amount": amount,
        "symbol": symbol,
        "has_value": has_value,
        "show_hint": has_value and irr_total is not None and irr_total >= 0,
        "irr_total": irr_total,
        "rate_hint": rate_hint if irr_total is not None else "",
    }
