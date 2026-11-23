from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.finance.models import PlatformFeeRule
from apps.finance.services import ton_exchange_rate as ter
from apps.finance.services.campaign_pricing import build_campaign_quote
import apps.finance.services.campaign_pricing as cp


@pytest.mark.django_db
@override_settings(PLATFORM_SERVICE_FEE_PERCENT=5, TON_PRICING_RISK_BUFFER_PERCENT=0, QUOTE_VALIDITY_SECONDS=300)
def test_build_campaign_quote_uses_active_platform_fee_rule(monkeypatch):
    PlatformFeeRule.objects.create(percent=9, is_active=True)
    snap = ter.TonRateSnapshot(
        source="nobitex",
        market_symbol="GRAMIRT",
        stats_pair="gram-rls",
        best_ask_irr=Decimal("1000000"),
        best_bid_irr=Decimal("999000"),
        last_trade_irr=Decimal("999500"),
        fetched_at=timezone.now(),
        provider_timestamp_ms=1,
        fetch_status="ok",
        is_fresh=True,
        exchange_rate_id="fee-test",
    )
    rate_stub = lambda ton, snapshot=None: {
        "rate_type": "best_ask",
        "effective_rate_irr": snap.best_ask_irr,
        "total_irr_for_ton": ton * snap.best_ask_irr,
        "base_rate_irr": snap.best_ask_irr,
        "snapshot": snap,
    }
    monkeypatch.setattr(cp, "get_pricing_snapshot", lambda **k: snap)
    monkeypatch.setattr(cp, "resolve_manual_snapshot", lambda: None)
    monkeypatch.setattr(cp, "effective_rate_for_ton", rate_stub)
    monkeypatch.setattr("apps.finance.services.gram_markup.gram_markup_factor", lambda: Decimal("1"))
    monkeypatch.setattr("apps.finance.services.gram_markup.apply_gram_markup_amount", lambda value: value)

    quote = build_campaign_quote(1_000_000)
    assert quote["fee_percent"] == 9
    assert quote["service_fee_irr"] == quote["advertising_budget_irr"] * 9 // 100
