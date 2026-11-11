from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import CustomerProfile, User
from apps.finance.models import ExchangeRate


@pytest.fixture(autouse=True)
def nobitex_pricing_stub(db, monkeypatch):
    """Deterministic Gram rate for tests — no live Nobitex HTTP."""
    now = timezone.now()
    details = {
        "irr_per_ton": 2_000_000,
        "best_ask_irr": "2000000",
        "best_bid_irr": "1990000",
        "last_trade_irr": "1995000",
        "source": "nobitex",
        "market_symbol": "GRAMIRT",
        "stats_pair": "gram-rls",
        "fetched_at": now.isoformat(),
        "fetch_status": "ok",
        "is_fresh": True,
    }
    row = ExchangeRate.objects.create(
        ton_per_irr=Decimal(1) / Decimal(2_000_000),
        source="nobitex",
        is_active=True,
        details=details,
    )
    details["exchange_rate_id"] = str(row.id)
    row.details = details
    row.save(update_fields=["details", "updated_at"])

    from apps.finance.services.ton_exchange_rate import TonRateSnapshot, get_pricing_snapshot

    def _effective_rate_for_ton(ton_amount, *, snapshot=None):
        snap = snapshot or get_pricing_snapshot(require_fresh=True)
        eff = snap.best_ask_irr
        return {
            "rate_type": "best_ask",
            "effective_rate_irr": eff,
            "total_irr_for_ton": ton_amount * eff,
            "base_rate_irr": snap.best_ask_irr,
            "snapshot": snap,
        }

    monkeypatch.setattr(
        "apps.finance.services.ton_exchange_rate.effective_rate_for_ton",
        _effective_rate_for_ton,
    )


@pytest.fixture
def customer_user(db):
    user = User.objects.create_user(username="cust1", password="pass1234", role=User.Role.CUSTOMER)
    return user


@pytest.fixture
def customer_profile(customer_user):
    return customer_user.customer_profile
