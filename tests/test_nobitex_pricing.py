from decimal import Decimal

import pytest

from apps.finance.exceptions import InsufficientLiquidityError, NobitexAPIError
from apps.finance.services.campaign_pricing import build_campaign_quote, quote_expired
from apps.finance.services.money import irr_to_toman_int, thousand_toman_to_irr
from apps.finance.services.nobitex_client import NobitexClient, _d
from apps.finance.services.ton_exchange_rate import compute_vwap_ask_cost


def test_decimal_parse_rejects_zero():
    assert _d("0") is None
    assert _d("-1") is None
    assert _d("5500000") == Decimal("5500000")


def test_vwap_depth():
    asks = [(Decimal("100"), Decimal("5")), (Decimal("110"), Decimal("10"))]
    cost, eff = compute_vwap_ask_cost(asks, Decimal("7"))
    assert cost == Decimal("5") * Decimal("100") + Decimal("2") * Decimal("110")
    assert eff == cost / Decimal("7")


def test_vwap_insufficient():
    with pytest.raises(InsufficientLiquidityError):
        compute_vwap_ask_cost([(Decimal("100"), Decimal("1"))], Decimal("5"))


def test_irr_toman():
    assert irr_to_toman_int(5_500_000) == 550_000
    assert thousand_toman_to_irr(100) == 1_000_000


@pytest.mark.django_db
def test_build_quote_locks_fields(monkeypatch):
    from django.utils import timezone

    from apps.finance.services import ton_exchange_rate as ter

    snap = ter.TonRateSnapshot(
        source="nobitex",
        market_symbol="GRAMIRT",
        stats_pair="gram-rls",
        best_ask_irr=Decimal("2850000"),
        best_bid_irr=Decimal("2840000"),
        last_trade_irr=Decimal("2845000"),
        fetched_at=timezone.now(),
        provider_timestamp_ms=1,
        fetch_status="ok",
        is_fresh=True,
        exchange_rate_id="test-id",
    )

    import apps.finance.services.campaign_pricing as cp

    monkeypatch.setattr(ter, "get_pricing_snapshot", lambda **k: snap)
    monkeypatch.setattr(ter, "resolve_manual_snapshot", lambda: None)
    monkeypatch.setattr(cp, "get_pricing_snapshot", lambda **k: snap)
    monkeypatch.setattr(cp, "resolve_manual_snapshot", lambda: None)
    monkeypatch.setattr("apps.finance.services.campaign_pricing.get_pricing_snapshot", lambda **k: snap)
    monkeypatch.setattr("apps.finance.services.campaign_pricing.resolve_manual_snapshot", lambda: None)
    rate_stub = lambda ton, snapshot=None: {
        "rate_type": "best_ask",
        "effective_rate_irr": snap.best_ask_irr,
        "total_irr_for_ton": ton * snap.best_ask_irr,
        "base_rate_irr": snap.best_ask_irr,
        "snapshot": snap,
    }
    monkeypatch.setattr(ter, "effective_rate_for_ton", rate_stub)
    monkeypatch.setattr(cp, "effective_rate_for_ton", rate_stub)
    monkeypatch.setattr("apps.finance.services.campaign_pricing.effective_rate_for_ton", rate_stub)

    budget = 2_850_000
    q = build_campaign_quote(budget)
    assert q["quote_status"] == "locked"
    assert q["total_irr"] > budget
    assert not quote_expired(q)


def test_quote_expired():
    from django.utils import timezone

    past = (timezone.now() - timezone.timedelta(minutes=1)).isoformat()
    assert quote_expired({"expires_at": past}) is True
    future = (timezone.now() + timezone.timedelta(minutes=5)).isoformat()
    assert quote_expired({"expires_at": future}) is False


def test_market_stats_ok(monkeypatch):
    class Resp:
        status_code = 200

        def json(self):
            return {
                "status": "ok",
                "stats": {
                    "gram-rls": {
                        "isClosed": False,
                        "bestSell": "100",
                        "bestBuy": "99",
                        "latest": "99",
                    }
                },
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, *args, **kwargs):
            return Resp()

    monkeypatch.setattr("apps.finance.services.nobitex_client.httpx.Client", FakeClient)
    stats = NobitexClient().fetch_market_stats()
    assert stats["best_ask_irr"] == Decimal("100")


def test_market_closed(monkeypatch):
    class Resp:
        status_code = 200

        def json(self):
            return {
                "status": "ok",
                "stats": {"gram-rls": {"isClosed": True, "bestSell": "100"}},
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, *args, **kwargs):
            return Resp()

    monkeypatch.setattr("apps.finance.services.nobitex_client.httpx.Client", FakeClient)
    with pytest.raises(NobitexAPIError):
        NobitexClient().fetch_market_stats()


def test_nobitex_client_validates_status(monkeypatch):
    class Resp:
        status_code = 200

        def json(self):
            return {"status": "failed", "code": "InvalidSymbol"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def get(self, *args, **kwargs):
            return Resp()

    monkeypatch.setattr("apps.finance.services.nobitex_client.httpx.Client", FakeClient)
    with pytest.raises(NobitexAPIError):
        NobitexClient().fetch_market_stats()
