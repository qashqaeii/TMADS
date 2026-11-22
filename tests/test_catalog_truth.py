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


def test_language_fallback_includes_persian_and_full_list():
    from apps.campaigns.catalog import FALLBACK_LANGUAGES, get_languages

    cache.clear()
    codes = {row["language_code"] for row in FALLBACK_LANGUAGES}
    assert "fa" in codes
    assert len(FALLBACK_LANGUAGES) >= 60
    with patch("apps.campaigns.catalog.TelegramAdsClient", side_effect=TelegramAdsError("offline")):
        rows = get_languages()
    assert any(row["language_code"] == "fa" for row in rows)
    assert len(rows) >= 60


def test_topic_rows_expose_persian_labels():
    from apps.campaigns.catalog import TOPIC_NAME_FA, _topic_row

    row = _topic_row({"topic_id": 29, "name": "Marketing & PR"})
    assert row["name_fa"] == "بازاریابی و روابط عمومی"
    assert TOPIC_NAME_FA[1] == "هنر و طراحی"
    assert _topic_row({"topic_id": 63, "name": "Other"})["name_fa"] == "سایر"


def test_channel_strategy_does_not_send_stale_inactive_fields():
    from apps.telegram_ads.targeting.builders import build_input_target

    cfg = parse_targeting_payload({"channel_mode":"language", "language_codes":["fa"],
        "channel_ids":"@telegram", "topic_ids":["4"], "exclude_channel_ids":"@first\n@second"}, "channels")
    # قانون تلگرام: با کانال مشخص، زبان/موضوع باید خالی شوند.
    assert cfg["language_codes"] == []
    assert cfg["channel_ids"] == ["@telegram"]
    assert cfg["topic_ids"] == []
    assert cfg["channel_mode"] == "specific"
    assert cfg["exclude_channel_ids"] == ["@first", "@second"]
    payload = build_input_target("channels", cfg).to_dict()
    assert payload["channel_ids"]
    assert "language_codes" not in payload or not payload.get("language_codes")
    assert "topic_ids" not in payload or not payload.get("topic_ids")


@pytest.mark.django_db
def test_live_catalog_rejects_location_in_different_country(customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, target_type="users")
    CampaignTargeting.objects.create(campaign=campaign, config={"country_codes":["IR"], "location_ids":[9001]})
    client = MagicMock()
    client.get_target_countries.return_value = [{"country_code":"IR"}]
    client.get_target_locations_by_ids.return_value = [{"location_id":9001,"country_code":"DE"}]
    with pytest.raises(ValueError):
        require_verified_catalog(campaign, client)
