from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.finance.models import GramRateMarkupRule
from apps.finance.services.campaign_pricing import build_campaign_quote
from apps.finance.services.gram_markup import (
    active_gram_markup_percent,
    apply_gram_markup_amount,
    snapshot_with_customer_markup,
)
from apps.finance.services.ton_exchange_rate import TonRateSnapshot


def _snap(ask: str = "2000000", *, source: str = "nobitex") -> TonRateSnapshot:
    return TonRateSnapshot(
        source=source,
        market_symbol="GRAMIRT" if source == "nobitex" else "manual",
        stats_pair="gram-rls" if source == "nobitex" else "manual",
        best_ask_irr=Decimal(ask),
        best_bid_irr=Decimal("1990000") if source == "nobitex" else None,
        last_trade_irr=Decimal("1995000") if source == "nobitex" else None,
        fetched_at=timezone.now(),
        provider_timestamp_ms=None,
        fetch_status="ok" if source == "nobitex" else "manual",
        is_fresh=True,
        exchange_rate_id=None,
    )


@pytest.mark.django_db
def test_markup_defaults_to_zero():
    assert active_gram_markup_percent() == 0
    assert apply_gram_markup_amount(Decimal("100")) == Decimal("100")


@pytest.mark.django_db
def test_active_markup_rule_applies_silently():
    GramRateMarkupRule.objects.create(percent=5, is_active=True)
    assert active_gram_markup_percent() == 5
    assert apply_gram_markup_amount(Decimal("2000000")) == Decimal("2100000")
    marked = snapshot_with_customer_markup(_snap())
    assert marked.irr_per_ton == 2100000
    assert marked.source == "nobitex"


@pytest.mark.django_db
def test_manual_snapshot_skips_markup():
    GramRateMarkupRule.objects.create(percent=5, is_active=True)
    manual = _snap(source="manual")
    assert snapshot_with_customer_markup(manual).best_ask_irr == Decimal("2000000")


@pytest.mark.django_db
@override_settings(GRAM_RATE_MARKUP_PERCENT=7)
def test_env_fallback_when_no_active_rule():
    assert active_gram_markup_percent() == 7


@pytest.mark.django_db
def test_quote_uses_marked_up_customer_rate(monkeypatch):
    import apps.finance.services.campaign_pricing as cp
    import apps.finance.services.ton_exchange_rate as ter

    GramRateMarkupRule.objects.create(percent=5, is_active=True)
    snap = _snap("2000000")
    monkeypatch.setattr(cp, "get_pricing_snapshot", lambda **k: snap)
    monkeypatch.setattr(cp, "resolve_manual_snapshot", lambda: None)
    monkeypatch.setattr(
        cp,
        "effective_rate_for_ton",
        lambda ton, snapshot=None: {
            "rate_type": "best_ask",
            "effective_rate_irr": snap.best_ask_irr,
            "total_irr_for_ton": ton * snap.best_ask_irr,
            "base_rate_irr": snap.best_ask_irr,
            "snapshot": snap,
        },
    )
    monkeypatch.setattr(ter, "get_pricing_snapshot", lambda **k: snap)
    monkeypatch.setattr(ter, "resolve_manual_snapshot", lambda: None)

    quote = build_campaign_quote(2_100_000)
    assert Decimal(quote["ton_allocation"]) == Decimal("1.00")
    assert quote["irr_per_ton"] == 2100000
