from decimal import Decimal

from apps.campaigns.analytics import (
    budget_consumption_tone,
    budget_is_depleted,
    budget_status_chip,
)


def test_depleted_when_remaining_zero():
    assert budget_is_depleted(spent_percent=100.0, remaining_ton=Decimal("0")) is True
    tone = budget_consumption_tone(spent_percent=100.0, remaining_ton=Decimal("0"))
    assert tone == "depleted"
    show, label = budget_status_chip(tone=tone, spent_percent=100.0)
    assert show is True
    assert label == "تمام"


def test_near_end_not_depleted_with_remainder():
    tone = budget_consumption_tone(spent_percent=95.0, remaining_ton=Decimal("1"))
    assert tone == "critical"
    show, label = budget_status_chip(tone=tone, spent_percent=95.0)
    assert show is True
    assert label == "نزدیک اتمام"


def test_high_tier():
    tone = budget_consumption_tone(spent_percent=80.0, remaining_ton=Decimal("5"))
    assert tone == "high"
    show, label = budget_status_chip(tone=tone, spent_percent=80.0)
    assert show is False
    assert label is None
