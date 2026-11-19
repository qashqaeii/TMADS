"""End-to-end dry-run journeys for four Telegram target types."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.campaigns.models import AdCreative, Campaign, CampaignTargeting
from apps.telegram_ads.services.ad_payload import build_create_ad_payload
from apps.telegram_ads.services.ad_write import dry_run_create_ad


def _dry_run(customer_user, **fields):
    targeting_config = fields.pop("targeting_config", None)
    needs_creative = fields.pop("needs_creative", True)
    ad_text = fields.pop("ad_text", "متن تبلیغ تست")
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        wizard_version=2,
        budget_irr=2_000_000,
        cpm_bid=Decimal("1.2"),
        destination="https://t.me/dest",
        name="V4 journey",
        ad_settings={"terms_accepted": True},
        **fields,
    )
    if targeting_config is not None:
        CampaignTargeting.objects.create(campaign=campaign, config=targeting_config)
    if needs_creative:
        AdCreative.objects.create(campaign=campaign, ad_text=ad_text)
    payload = build_create_ad_payload(campaign, include_initial_budget=False)
    dry = dry_run_create_ad(campaign)
    return campaign, payload, dry


@pytest.mark.django_db
def test_journey_search(customer_user):
    _, payload, dry = _dry_run(
        customer_user,
        target_type=Campaign.TargetType.SEARCH,
        placement="search_result",
        needs_creative=False,
        targeting_config={"search_queries": ["کفش", "ورزش"]},
    )
    assert payload["target"]["type"] == "search"
    assert dry["ok"] is True
    assert "schedule" not in payload or payload.get("schedule") is None


@pytest.mark.django_db
@patch("apps.telegram_ads.services.bot_eligibility.check_bot_eligibility")
def test_journey_bots(mock_check, customer_user):
    mock_check.return_value = MagicMock(
        hard_block=False,
        bot={"title": "My Bot"},
        message_fa="ok",
    )
    _, payload, dry = _dry_run(
        customer_user,
        target_type=Campaign.TargetType.BOTS,
        placement="bot_banner",
        targeting_config={"bot_ids": ["@mybot"]},
    )
    assert payload["target"]["type"] == "bots"
    assert payload.get("text")
    assert dry["ok"] is True


@pytest.mark.django_db
def test_journey_users_with_schedule(customer_user):
    campaign, payload, dry = _dry_run(
        customer_user,
        target_type=Campaign.TargetType.USERS,
        placement="channel_post",
        targeting_config={
            "country_codes": ["IR"],
            "topic_ids": [1],
            "placement_api": "channel_post",
        },
    )
    campaign.ad_settings = {
        **campaign.ad_settings,
        "schedule": {
            "week_hours_mask": [0, 0, 0, 0, 0, 0, 0],
            "timezone": 12600,
        },
    }
    campaign.ad_settings["schedule"]["week_hours_mask"][0] = sum(1 << h for h in range(9, 12))
    campaign.save(update_fields=["ad_settings", "updated_at"])
    payload2 = build_create_ad_payload(campaign, include_initial_budget=False)
    assert payload2["target"]["type"] == "users"
    assert "schedule" in payload2
    assert dry["ok"] is True


@pytest.mark.django_db
def test_journey_channels(customer_user):
    _, payload, dry = _dry_run(
        customer_user,
        target_type=Campaign.TargetType.CHANNELS,
        placement="channel_post",
        targeting_config={"channel_mode": "language", "language_codes": ["fa"]},
    )
    assert payload["target"]["type"] == "channels"
    assert dry["ok"] is True


@pytest.mark.django_db
def test_catalog_countries_fallback(client, customer_user):
    client.login(username=customer_user.username, password="pass1234")
    from django.urls import reverse

    url = reverse("campaigns:catalog_countries")
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert len(data["items"]) >= 1
