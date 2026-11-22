"""Similar Channels — getSimilarChannels + language exclusivity."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.campaigns.models import Campaign
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.similar_channels import (
    SimilarChannelsService,
    _parse_api_rows,
    _row_subscribers,
    _row_username,
)
from apps.telegram_ads.targeting.validators import validate_audience_step


@pytest.fixture(autouse=True)
def clear_caches():
    cache.clear()
    yield
    cache.clear()


SAMPLE_API = {
    "ok": True,
    "channels": [
        {
            "val": "3v5rsCxzf9s5gEUcxuZkY9q_Pt0sQDAa67d9zBeFBEk",
            "name": "ایران موبایل",
            "photo": '<img src="https://cdn4.telesco.pe/file/sample.jpg" />',
            "username": "iranmob_1",
            "cb_item": (
                '<span class="pr-similar-channel-desc">13,937 subscribers</span>'
            ),
        },
        {
            "val": "tbij4hMhpyU6bFVVYpBIyqZX_-STWrWGmCpedtYtD_o",
            "name": "schematic",
            "photo": "",
            "username": "phoneschematic",
            "cb_item": '<span class="pr-similar-channel-desc">21,930 subscribers</span>',
        },
    ],
}


def test_parse_api_rows_and_username_not_from_title():
    rows = _parse_api_rows(SAMPLE_API)
    assert len(rows) == 2
    assert _row_username(rows[0]) == "@iranmob_1"
    assert _row_username({"name": "ایران موبایل"}) is None
    assert _row_subscribers(rows[0]) == 13937


def test_channels_language_must_be_empty_with_specific_channels():
    result = validate_audience_step(
        target_type="channels",
        placement="channel_post",
        config={
            "channel_ids": ["@telegram"],
            "language_codes": ["fa"],
            "topic_ids": [],
        },
        strict=True,
    )
    assert not result.ok
    assert any("زبان" in err for err in result.errors)

    clean = validate_audience_step(
        target_type="channels",
        placement="channel_post",
        config={"channel_ids": ["@telegram"], "language_codes": [], "topic_ids": []},
        strict=True,
    )
    assert clean.ok or not any("زبان" in err for err in clean.errors)


def test_channels_topics_must_be_empty_with_specific_channels():
    result = validate_audience_step(
        target_type="channels",
        placement="channel_post",
        config={
            "channel_ids": ["@telegram"],
            "language_codes": [],
            "topic_ids": [4],
        },
        strict=True,
    )
    assert not result.ok
    assert any("موضوع" in err for err in result.errors)


@patch("apps.telegram_ads.client.TelegramAdsClient")
def test_similar_channels_service_uses_api(mock_client_cls):
    client = MagicMock()
    mock_client_cls.return_value = client
    client.resolve_target_channel.side_effect = [
        # شناسه واقعی کانال‌های تلگرام منفی است
        {"channel_id": -1002258272508, "username": "seedchan", "title": "Seed", "photo_url": ""},
        {
            "channel_id": -100101,
            "username": "iranmob_1",
            "title": "ایران موبایل",
            "photo_url": "https://cdn4.telesco.pe/file/sample.jpg",
        },
        {
            "channel_id": -100102,
            "username": "phoneschematic",
            "title": "schematic",
            "photo_url": "",
        },
    ]
    client.get_similar_channels.return_value = SAMPLE_API

    result = SimilarChannelsService().get_similar("@seedchan", use_cache=False, limit=12)
    assert result.ok
    assert result.reason == "ok"
    assert len(result.items) == 2
    assert result.items[0].username == "@iranmob_1"
    assert result.items[0].subscribers == 13937
    assert result.items[0].channel_id == -100101
    client.get_similar_channels.assert_called_once()


def test_negative_telegram_channel_id_is_valid():
    from apps.telegram_ads.services.similar_channels import _is_resolved_channel_id

    assert _is_resolved_channel_id(-1002258272508) is True
    assert _is_resolved_channel_id(0) is False
    assert _is_resolved_channel_id(None) is False


@patch("apps.telegram_ads.client.TelegramAdsClient")
def test_similar_channels_api_unavailable_falls_back_empty(mock_client_cls):
    client = MagicMock()
    mock_client_cls.return_value = client
    client.resolve_target_channel.return_value = {
        "channel_id": 100,
        "username": "seedchan",
        "title": "Seed",
        "photo_url": "",
    }
    client.get_similar_channels.side_effect = TelegramAdsError("no method")

    result = SimilarChannelsService().get_similar("@seedchan", use_cache=False)
    assert result.ok
    assert result.items == []
    assert result.reason == "empty"


@pytest.mark.django_db
def test_studio_channels_similar_endpoint(client, customer_user):
    client.force_login(customer_user)
    url = reverse("campaigns:channels_similar")
    with patch(
        "apps.telegram_ads.services.similar_channels.SimilarChannelsService.get_similar"
    ) as mocked:
        from apps.telegram_ads.services.similar_channels import (
            SimilarChannelItem,
            SimilarChannelsResult,
        )

        mocked.return_value = SimilarChannelsResult(
            ok=True,
            seed="@seedchan",
            items=[
                SimilarChannelItem(
                    username="@iranmob_1",
                    title="ایران موبایل",
                    photo_url="https://cdn4.telesco.pe/file/sample.jpg",
                    channel_id=101,
                    subscribers=13937,
                    score=100,
                    reasons=["api"],
                )
            ],
            message_fa="1 کانال مشابه پیدا شد.",
            reason="ok",
        )
        response = client.post(
            url,
            {
                "seed": "@seedchan",
                "exclude": json.dumps(["@other"]),
                "limit": "12",
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["items"][0]["username"] == "@iranmob_1"
    assert body["items"][0]["subscribers"] == 13937


@pytest.mark.django_db
def test_studio_channels_similar_disabled(client, customer_user, settings):
    settings.SIMILAR_CHANNELS_ENABLED = False
    client.force_login(customer_user)
    response = client.post(
        reverse("campaigns:channels_similar"),
        {"seed": "@seedchan"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["feature_enabled"] is False
    assert body["items"] == []


@pytest.mark.django_db
def test_channels_wizard_has_similar_markup(client, customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="کانال مشابه",
        target_type=Campaign.TargetType.CHANNELS,
        placement="channel_post",
        wizard_version=2,
        wizard_step=2,
    )
    client.force_login(customer_user)
    html = client.get(reverse("campaigns:wizard", kwargs={"campaign_id": campaign.id})).content.decode()
    assert "data-similar-channels-panel" in html
    assert "افزودن کانال‌های مشابه" in html
