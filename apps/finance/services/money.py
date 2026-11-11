from __future__ import annotations

from decimal import Decimal, ROUND_CEILING

IRR_PER_TOMAN = 10


def toman_to_irr(toman: int) -> int:
    return int(toman) * IRR_PER_TOMAN


def thousand_toman_to_irr(thousand_toman: int) -> int:
    """Wizard stores budget as thousand toman × 10_000 → IRR."""
    return int(thousand_toman) * 10_000


def irr_to_toman_int(irr: int) -> int:
    return int(irr) // IRR_PER_TOMAN


def ceil_irr(amount: Decimal) -> int:
    return int(amount.to_integral_value(rounding=ROUND_CEILING))
