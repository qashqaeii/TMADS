from unittest.mock import MagicMock, patch
import pytest
from django.core.cache import cache
from apps.campaigns.catalog import get_topics, search_locations
from apps.campaigns.studio import parse_targeting_payload
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.catalog_verification import require_verified_catalog
from apps.campaigns.models import Campaign, CampaignTargeting


def test_catalog_never_fabricates_ids():
    cache.clear()
    with patch("apps.campaigns.catalog.TelegramAdsClient", side_effect=TelegramAdsError("offline")):
        assert get_topics() == []
        assert search_locations("IR", "Tehran") == []
        with pytest.raises(TelegramAdsError):
            search_locations("IR", "Tehran", raise_on_unavailable=True)


def test_channel_strategy_does_not_send_stale_inactive_fields():
    cfg = parse_targeting_payload({"channel_mode":"language", "language_codes":["fa"],
        "channel_ids":"@telegram", "topic_ids":["4"], "exclude_channel_ids":"@first\n@second"}, "channels")
    assert cfg["language_codes"] == ["fa"]
    assert cfg["channel_ids"] == [] and cfg["topic_ids"] == []
    assert cfg["exclude_channel_ids"] == ["@first", "@second"]


@pytest.mark.django_db
def test_live_catalog_rejects_location_in_different_country(customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, target_type="users")
    CampaignTargeting.objects.create(campaign=campaign, config={"country_codes":["IR"], "location_ids":[9001]})
    client = MagicMock()
    client.get_target_countries.return_value = [{"country_code":"IR"}]
    client.get_target_locations_by_ids.return_value = [{"location_id":9001,"country_code":"DE"}]
    with pytest.raises(ValueError):
        require_verified_catalog(campaign, client)
