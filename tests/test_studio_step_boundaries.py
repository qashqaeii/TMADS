"""Regression coverage for actual studio step boundaries."""
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.campaigns.models import Campaign, CampaignTargeting, AdCreative
from apps.campaigns.studio import validate_studio_step


@pytest.mark.django_db
@pytest.mark.parametrize("target,placement,fields", [
    ("search", "search_result", {"search_queries_json": '["test"]'}),
    ("bots", "bot_banner", {"bot_ids": "@vote"}),
    ("channels", "channel_post", {"channel_mode": "language", "language_codes": "fa"}),
    ("users", "channel_post", {"country_codes": "IR"}),
])
def test_actual_audience_post_advances_without_creative_or_terms(client, customer_user, target, placement, fields):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile, name="Step boundaries",
        target_type=target, placement=placement, destination="https://t.me/test",
        wizard_step=2, wizard_version=2,
    )
    client.force_login(customer_user)
    with patch("apps.telegram_ads.services.bot_eligibility.validate_bot_targets", return_value=[]):
        response = client.post(reverse("campaigns:wizard", args=[campaign.id]), {
            "action": "next", "placement": placement, "draft_revision": 0, "studio_step": 2, **fields,
        })
    campaign.refresh_from_db()
    assert response.status_code == 302
    assert campaign.wizard_step == 3
    assert not campaign.creatives.exists()
    assert not campaign.ad_settings.get("terms_accepted")


@pytest.mark.django_db
def test_stepper_goto_allows_jump_within_furthest(client, customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="Stepper jump",
        target_type="channels",
        placement="channel_post",
        destination="https://t.me/test",
        wizard_step=3,
        wizard_version=2,
        wizard_data={"studio_furthest_step": 4},
    )
    CampaignTargeting.objects.create(campaign=campaign, config={"language_codes": ["fa"]})
    AdCreative.objects.create(campaign=campaign, ad_text="متن آزمایشی تبلیغ")
    client.force_login(customer_user)

    html = client.get(reverse("campaigns:wizard", args=[campaign.id])).content.decode()
    assert 'name="goto_step" value="1"' in html
    assert 'name="goto_step" value="2"' in html
    assert 'name="goto_step" value="4"' in html
    assert 'name="goto_step" value="5"' not in html
    assert 'aria-current="step"' in html

    response = client.post(
        reverse("campaigns:wizard", args=[campaign.id]),
        {
            "goto_step": "1",
            "draft_revision": campaign.draft_revision,
            "studio_step": 3,
            "ad_text": "متن آزمایشی تبلیغ",
        },
    )
    campaign.refresh_from_db()
    assert response.status_code == 302
    assert campaign.wizard_step == 1
    assert (campaign.wizard_data or {}).get("studio_furthest_step") == 4


@pytest.mark.django_db
def test_final_validation_does_not_change_budget_or_schedule(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile, name="Review",
        target_type="channels", placement="channel_post", destination="https://t.me/test",
        wizard_step=5, wizard_version=2, budget_irr=2_000_000,
        daily_cap_irr=100_000, ad_settings={"schedule": {"week_hours_mask": [1] * 7}},
    )
    CampaignTargeting.objects.create(campaign=campaign, config={"language_codes": ["fa"]})
    AdCreative.objects.create(campaign=campaign, ad_text="Test advertisement")
    before = (campaign.budget_irr, campaign.daily_cap_irr, campaign.ad_settings)
    assert not validate_studio_step(campaign, 5, {"terms_accepted": "1"}, strict=True)
    campaign.refresh_from_db()
    assert (campaign.budget_irr, campaign.daily_cap_irr, campaign.ad_settings) == before
