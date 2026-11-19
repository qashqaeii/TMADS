import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from apps.campaigns.models import Campaign, CampaignTargeting
from apps.campaigns.studio import apply_studio_step, parse_targeting_payload
from apps.telegram_ads.services.ad_payload import build_create_ad_payload
from apps.telegram_ads.services.ad_write import ExecutionMode, dry_run_create_ad, execute_create_ad
from apps.telegram_ads.targeting.builders import build_input_target
from apps.telegram_ads.targeting.validators import validate_studio_config
from telead.inputs import InputAdTargetSearch


@pytest.mark.django_db
def test_search_target_builder_and_payload(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="جستجوی تست",
        target_type=Campaign.TargetType.SEARCH,
        placement="search_result",
        destination="https://t.me/testbot",
        budget_irr=5_000_000,
        cpm_bid=Decimal("1.5"),
        wizard_version=2,
    )
    CampaignTargeting.objects.create(
        campaign=campaign,
        config={"search_queries": ["کفش", "ورزش"]},
    )
    from apps.campaigns.models import AdCreative

    AdCreative.objects.create(campaign=campaign, ad_text="ignored for search")
    campaign.ad_settings = {"terms_accepted": True}
    campaign.save(update_fields=["ad_settings"])

    result = validate_studio_config(
        target_type="search",
        placement="search_result",
        config=campaign.targeting.config,
        promote_url=campaign.destination,
        strict=True,
        ad_settings={"terms_accepted": True},
    )
    assert result.ok

    payload = build_create_ad_payload(campaign, include_initial_budget=False)
    assert payload["target"]["type"] == "search"
    assert "text" not in payload or payload.get("text") is None
    assert payload["placement"] == "search_result"

    dry = dry_run_create_ad(campaign)
    assert dry["ok"] is True
    assert dry["api_method"] == "createAd"


@pytest.mark.django_db
@patch("apps.telegram_ads.services.bot_eligibility.check_bot_eligibility")
def test_bot_target_requires_bots(mock_check, customer_user):
    mock_check.return_value = MagicMock(
        hard_block=False,
        bot={"title": "My Bot"},
        message_fa="ok",
    )
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        target_type=Campaign.TargetType.BOTS,
        placement="bot_banner",
        destination="https://t.me/foo",
        name="Bot ad",
        wizard_version=2,
        budget_irr=2_000_000,
        cpm_bid=Decimal("1"),
    )
    from apps.campaigns.models import AdCreative

    AdCreative.objects.create(campaign=campaign, ad_text="سلام از ربات")
    CampaignTargeting.objects.create(campaign=campaign, config={"bot_ids": ["@mybot"]})
    campaign.ad_settings = {"terms_accepted": True}
    campaign.save(update_fields=["ad_settings"])

    payload = build_create_ad_payload(campaign, include_initial_budget=False)
    assert payload["target"]["type"] == "bots"
    assert payload["text"] == "سلام از ربات"


@pytest.mark.django_db
def test_users_channel_mode_validation(customer_user):
    cfg = {
        "country_codes": ["IR"],
        "topic_ids": [1, 2],
        "placement_api": "channel_post",
    }
    result = validate_studio_config(
        target_type="users",
        placement="channel_post",
        config=cfg,
        promote_url="https://t.me/channel",
        ad_text="متن",
        strict=True,
        ad_settings={"terms_accepted": True},
    )
    assert result.ok
    target = build_input_target("users", cfg)
    target.validate()


@pytest.mark.django_db
def test_channels_exclusive_modes():
    from telead.inputs import InputAdTargetChannels

    with pytest.raises(Exception):
        InputAdTargetChannels(channel_ids=["@a"], language_codes=["fa"]).validate()

    ch = build_input_target(
        "channels",
        {"channel_mode": "specific", "channel_ids": ["@telegram"]},
    )
    ch.validate()
    assert ch.to_dict()["channel_ids"]


@pytest.mark.django_db
def test_wizard_autosave_and_draft(client, customer_user):
    client.login(username=customer_user.username, password="pass1234")
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        wizard_version=2,
        target_type="search",
        wizard_step=1,
    )
    url = reverse("campaigns:autosave", kwargs={"campaign_id": campaign.id})
    response = client.post(
        url,
        {
            "draft_revision": "0",
            "target_type": "search",
            "destination": "https://t.me/x",
            "campaign_name": "autosave",
        },
    )
    assert response.status_code == 200
    campaign.refresh_from_db()
    assert campaign.draft_revision == 1
    assert campaign.destination.startswith("https://")


@pytest.mark.django_db
def test_execute_create_ad_mocked_live(customer_user, settings):
    settings.TELEGRAM_ADS_WRITE_ENABLED = True
    settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED = True
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        target_type=Campaign.TargetType.BOTS,
        placement="bot_banner",
        destination="https://t.me/bot",
        name="Live mock",
        budget_irr=1_000_000,
        cpm_bid=Decimal("1"),
        wizard_version=2,
    )
    from apps.campaigns.models import AdCreative

    AdCreative.objects.create(campaign=campaign, ad_text="txt")
    CampaignTargeting.objects.create(campaign=campaign, config={"bot_ids": ["@b"]})
    campaign.ad_settings = {"terms_accepted": True}
    campaign.save()

    with patch("apps.telegram_ads.services.ad_write.TelegramAdsClient") as ClientCls:
        instance = ClientCls.return_value
        instance.create_advertisement.return_value = {"ad_id": 99, "status": "on_hold"}
        out = execute_create_ad(campaign, mode=ExecutionMode.LIVE)
        assert out["remote_ad_id"] == "99"
        instance.create_advertisement.assert_called_once()


@pytest.mark.django_db
def test_search_query_limit():
    queries = [f"q{i}" for i in range(11)]
    t = InputAdTargetSearch(search_queries=queries)
    with pytest.raises(Exception):
        t.validate()


@pytest.mark.django_db
def test_studio_step_flow_quote(client, customer_user):
    client.login(username=customer_user.username, password="pass1234")
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        wizard_version=2,
        wizard_step=4,
        budget_irr=1_000_000,
        target_type="channels",
        placement="channel_post",
        destination="https://t.me/ch",
    )
    from apps.campaigns.models import AdCreative

    AdCreative.objects.create(campaign=campaign, ad_text="ad")
    CampaignTargeting.objects.create(campaign=campaign, config={"language_codes": ["fa"]})
    url = reverse("campaigns:wizard", kwargs={"campaign_id": campaign.id})
    client.post(url, {"action": "next", "budget_toman": "100", "cpm_bid": "1"})
    campaign.refresh_from_db()
    assert campaign.wizard_step == 5
    assert campaign.status == Campaign.Status.AWAITING_PAYMENT
