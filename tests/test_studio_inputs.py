import pytest
from django.urls import reverse
from apps.campaigns.models import Campaign
from apps.campaigns.studio import apply_studio_step, validate_budget_inputs


@pytest.mark.django_db
@pytest.mark.parametrize("fields", [
    {"budget_toman": "-10"}, {"cpm_bid": "NaN"}, {"schedule_start": "invalid"}, {"daily_cap_toman": "150"},
])
def test_invalid_budget_fields(customer_user, fields):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, budget_irr=1_000_000)
    assert validate_budget_inputs(campaign, {"budget_toman":"100", **fields}, strict=True)


@pytest.mark.django_db
def test_review_cannot_replace_schedule_or_placement(customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, target_type="search",
        budget_irr=1_000_000, daily_cap_irr=100_000, ad_settings={"remote_initial_status":"on_hold"})
    apply_studio_step(campaign, 5, {"terms_accepted":"1","remote_initial_status":"active","budget_toman":"999"})
    campaign.refresh_from_db()
    assert campaign.budget_irr == 1_000_000
    assert campaign.ad_settings["remote_initial_status"] == "on_hold"
