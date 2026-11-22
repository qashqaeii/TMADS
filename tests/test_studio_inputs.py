import pytest
from decimal import Decimal

from apps.campaigns.models import Campaign
from apps.campaigns.studio import (
    apply_studio_step,
    parse_studio_decimal_amount,
    parse_studio_int_amount,
    validate_budget_inputs,
)


@pytest.mark.django_db
@pytest.mark.parametrize("fields", [
    {"budget_toman": "-10"}, {"cpm_bid": "NaN"}, {"schedule_start": "invalid"}, {"daily_cap_toman": "400000"}, {"budget_toman": "100000"},
])
def test_invalid_budget_fields(customer_user, fields):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, budget_irr=1_000_000)
    assert validate_budget_inputs(campaign, {"budget_toman":"200000", **fields}, strict=True)


def test_studio_amount_parsers_accept_grouped_persian_digits():
    assert parse_studio_int_amount("۵۰۰٬۰۰۰") == 500000
    assert parse_studio_int_amount("500,000") == 500000
    assert parse_studio_decimal_amount("۱٫۵۰") == Decimal("1.50")
    assert parse_studio_decimal_amount("1,234.5") == Decimal("1234.5")


@pytest.mark.django_db
def test_budget_minimum_is_one_ton_equivalent(customer_user):
    from apps.finance.services.money import minimum_advertising_budget_irr, toman_to_irr

    campaign = Campaign.objects.create(customer=customer_user.customer_profile, budget_irr=0)
    min_irr = minimum_advertising_budget_irr()
    assert min_irr == 2_000_000  # conftest stub rate
    too_low = validate_budget_inputs(campaign, {"budget_toman": "199999"}, strict=True)
    assert any("۱ گرام" in e for e in too_low)
    assert not validate_budget_inputs(
        campaign,
        {"budget_toman": str(min_irr // 10), "cpm_bid": "1", "impression_frequency": "1"},
        strict=True,
    )
    assert toman_to_irr(200000) >= min_irr


@pytest.mark.django_db
def test_apply_step4_accepts_formatted_budget(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        budget_irr=1_000_000,
        wizard_version=2,
        wizard_step=4,
    )
    apply_studio_step(
        campaign,
        4,
        {
            "budget_toman": "۵۰۰٬۰۰۰",
            "daily_cap_toman": "200,000",
            "cpm_bid": "۱٫۲۵",
            "impression_frequency": "1",
            "remote_initial_status": "active",
        },
    )
    campaign.refresh_from_db()
    assert campaign.budget_irr == 500000 * 10
    assert campaign.daily_cap_irr == 200000 * 10
    assert campaign.cpm_bid == Decimal("1.25")


@pytest.mark.django_db
def test_review_cannot_replace_schedule_or_placement(customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, target_type="search",
        budget_irr=1_000_000, daily_cap_irr=100_000, ad_settings={"remote_initial_status":"on_hold"})
    apply_studio_step(campaign, 5, {"terms_accepted":"1","remote_initial_status":"active","budget_toman":"999"})
    campaign.refresh_from_db()
    assert campaign.budget_irr == 1_000_000
    assert campaign.ad_settings["remote_initial_status"] == "on_hold"
