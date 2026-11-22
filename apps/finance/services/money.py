from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

IRR_PER_TOMAN = 10
MIN_CAMPAIGN_BUDGET_TON = Decimal("1")


def toman_to_irr(toman: int) -> int:
    return int(toman) * IRR_PER_TOMAN


def thousand_toman_to_irr(thousand_toman: int) -> int:
    """Legacy helper: 1 thousand toman = 1_000 toman = 10_000 IRR."""
    return toman_to_irr(int(thousand_toman) * 1_000)


def irr_to_toman_int(irr: int) -> int:
    return int(irr) // IRR_PER_TOMAN


def ceil_irr(amount: Decimal) -> int:
    return int(amount.to_integral_value(rounding=ROUND_CEILING))


def minimum_advertising_budget_irr() -> int:
    """Minimum campaign advertising budget: equivalent of 1 Gram/TON at current rate."""
    from apps.finance.services import resolve_irr_per_ton

    rate = int(resolve_irr_per_ton() or 0)
    if rate <= 0:
        return 0
    return ceil_irr(MIN_CAMPAIGN_BUDGET_TON * Decimal(rate))


def minimum_advertising_budget_toman() -> int:
    return irr_to_toman_int(minimum_advertising_budget_irr())
