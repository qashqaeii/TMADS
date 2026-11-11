from decimal import Decimal

import pytest

from apps.finance.models import ExchangeRate
from apps.finance.services.ton_equiv import (
    irr_per_ton_from_exchange_id,
    resolve_ton_display_rate,
    ton_amount_to_irr,
)


@pytest.mark.django_db
def test_irr_per_ton_from_exchange_id():
    row = ExchangeRate.objects.create(
        ton_per_irr=Decimal("0.0000001"),
        source="manual",
        is_active=True,
        details={"irr_per_ton": 12_500_000},
    )
    assert irr_per_ton_from_exchange_id(row.id) == 12_500_000
    assert irr_per_ton_from_exchange_id(None) is None


def test_ton_amount_to_irr():
    assert ton_amount_to_irr(Decimal("2"), 10_000_000) == 20_000_000
    assert ton_amount_to_irr(None, 10_000_000) is None


def test_resolve_ton_display_rate_explicit():
    irr, hint = resolve_ton_display_rate(rate_irr=9_000_000)
    assert irr == 9_000_000
    assert "نرخ" in hint
