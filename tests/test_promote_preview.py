"""Promote destination preview — official API photo/title only."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.telegram_ads.services.promote_preview import resolve_promote_preview


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@patch("apps.telegram_ads.services.promote_preview.TelegramAdsClient")
def test_resolve_bot_photo_https_only(mock_client_cls):
    mock_client_cls.return_value.resolve_target_bot.return_value = {
        "bot_id": 123,
        "title": "HyperTunnel",
        "username": "HyperTunnelbot",
        "photo_url": "https://cdn.example.com/a.jpg",
    }
    out = resolve_promote_preview("https://t.me/HyperTunnelbot")
    assert out["ok"] is True
    assert out["kind"] == "bot"
    assert out["title"] == "HyperTunnel"
    assert out["photo_url"] == "https://cdn.example.com/a.jpg"


@patch("apps.telegram_ads.services.promote_preview.TelegramAdsClient")
def test_rejects_non_https_photo(mock_client_cls):
    mock_client_cls.return_value.resolve_target_bot.return_value = {
        "bot_id": 123,
        "title": "Bot",
        "photo_url": "javascript:alert(1)",
    }
    out = resolve_promote_preview("@SomeBot")
    assert out["ok"] is True
    assert out["photo_url"] == ""


@patch("apps.telegram_ads.services.promote_preview.TelegramAdsClient")
def test_endpoint_auth_and_shape(mock_client_cls, client, customer_user):
    mock_client_cls.return_value.resolve_target_bot.return_value = {
        "bot_id": 9,
        "title": "HyperTunnel",
        "photo_url": "https://cdn.example.com/p.jpg",
    }
    url = reverse("campaigns:promote_preview")
    assert client.get(url, {"destination": "t.me/HyperTunnelbot"}).status_code in {302, 401, 403}
    client.force_login(customer_user)
    res = client.get(url, {"destination": "t.me/HyperTunnelbot"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["photo_url"].startswith("https://")
    assert "cb_item" not in body
