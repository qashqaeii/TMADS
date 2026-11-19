"""Bot targeting eligibility — official getTargetBot only."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.campaigns.catalog import resolve_bot
from apps.telegram_ads.exceptions import (
    TelegramAdsApiError,
    TelegramAdsNotConfigured,
    TelegramAdsTransportError,
)
from apps.telegram_ads.services.bot_eligibility import (
    check_bot_eligibility,
    validate_bot_targets,
)
from apps.telegram_ads.targeting.normalize import parse_bot_peer_input
from apps.telegram_ads.targeting.validators import validate_studio_config


@pytest.fixture(autouse=True)
def clear_bot_elig_cache():
    cache.clear()
    yield
    cache.clear()


def test_parse_bot_peer_input_accepts_tme_and_at():
    at, api = parse_bot_peer_input("https://t.me/VoteBot")
    assert at == "@VoteBot"
    assert api == "@VoteBot"
    at2, _ = parse_bot_peer_input("@VoteBot")
    assert at2 == "@VoteBot"


def test_resolve_bot_uses_client_wrapper_not_raw_get(monkeypatch):
    calls = []

    def fake_check(value, *, use_cache=True):
        calls.append(("check", value, use_cache))
        return MagicMock(
            to_json=lambda: {"ok": True, "eligibility": "eligible", "username": "@vote"},
        )

    monkeypatch.setattr("apps.campaigns.catalog.check_bot_eligibility", fake_check)
    out = resolve_bot("@vote")
    assert out["eligibility"] == "eligible"
    assert calls and calls[0][0] == "check"
    # Regression: catalog must not call client.get_target_bot (removed from module).
    import apps.campaigns.catalog as catalog_mod

    assert not hasattr(catalog_mod, "get_target_bot")


@patch("apps.telegram_ads.services.bot_eligibility.TelegramAdsClient")
def test_eligible_bot_with_explicit_api_success(mock_client_cls):
    mock_client_cls.return_value.resolve_target_bot.return_value = {
        "bot_id": 129782279,
        "title": "VoteBot",
        "username": "vote",
    }
    result = check_bot_eligibility("@vote", use_cache=False)
    assert result.eligibility == "eligible"
    assert result.verified is True
    assert result.bot["bot_id"] == 129782279
    mock_client_cls.return_value.resolve_target_bot.assert_called_once_with("@vote")


@patch("apps.telegram_ads.services.bot_eligibility.TelegramAdsClient")
def test_insufficient_audience_bot_too_small(mock_client_cls):
    mock_client_cls.return_value.resolve_target_bot.side_effect = TelegramAdsApiError(
        "BOT_TOO_SMALL",
        description="Target bot must have 1000+ daily users.",
        method="getTargetBot",
    )
    result = check_bot_eligibility("@SmallBot", use_cache=False)
    assert result.eligibility == "insufficient_audience"
    assert result.hard_block is True
    assert result.api_code == "BOT_TOO_SMALL"
    assert "حداقل مخاطب" in result.message_fa


@patch("apps.telegram_ads.services.bot_eligibility.TelegramAdsClient")
def test_invalid_username(mock_client_cls):
    mock_client_cls.return_value.resolve_target_bot.side_effect = TelegramAdsApiError(
        "USERNAME_INVALID",
        method="getTargetBot",
    )
    result = check_bot_eligibility("@not_real_zzzzz", use_cache=False)
    assert result.eligibility == "invalid_bot"
    assert result.verified is True


@patch("apps.telegram_ads.services.bot_eligibility.TelegramAdsClient")
def test_network_timeout_not_ineligible(mock_client_cls):
    mock_client_cls.return_value.resolve_target_bot.side_effect = TelegramAdsTransportError(
        "اتصال برقرار نشد"
    )
    result = check_bot_eligibility("@vote", use_cache=False)
    assert result.eligibility == "api_unavailable"
    assert result.hard_block is False


@patch("apps.telegram_ads.services.bot_eligibility.TelegramAdsClient")
def test_permission_error_api_unavailable(mock_client_cls):
    mock_client_cls.return_value.resolve_target_bot.side_effect = TelegramAdsApiError(
        "ACCESS_DENIED",
        method="getTargetBot",
    )
    result = check_bot_eligibility("@vote", use_cache=False)
    assert result.eligibility == "api_unavailable"
    assert result.hard_block is False


def test_invalid_local_input_without_api_call():
    result = check_bot_eligibility("!!!", use_cache=False)
    assert result.eligibility == "invalid_bot"
    assert result.verified is True


@patch("apps.telegram_ads.services.bot_eligibility.TelegramAdsClient")
def test_programming_error_not_swallowed_as_eligibility(mock_client_cls):
    mock_client_cls.return_value.resolve_target_bot.side_effect = RuntimeError("unexpected")
    with pytest.raises(RuntimeError):
        check_bot_eligibility("@vote", use_cache=False)


@patch("apps.telegram_ads.services.bot_eligibility.check_bot_eligibility")
def test_validate_bot_targets_hard_blocks_only_verified_failures(mock_check):
    mock_check.side_effect = [
        MagicMock(hard_block=True, bot={"title": "X"}, message_fa="blocked"),
        MagicMock(hard_block=False, bot={}, message_fa="ok"),
    ]
    errors = validate_bot_targets(["@vote", "@gif"], strict=True)
    assert len(errors) == 1
    assert "blocked" in errors[0]


def test_validate_studio_multiple_bots_and_draft_checks():
    cfg = {
        "bot_ids": ["@vote", "@gif"],
        "bot_peer_checks": {
            "@vote": {"eligibility": "api_unavailable", "hard_block": False},
        },
    }
    with patch("apps.telegram_ads.services.bot_eligibility.check_bot_eligibility") as checker:
        checker.return_value = MagicMock(hard_block=False, eligibility="api_unavailable")
        result = validate_studio_config(
            target_type="bots",
            placement="bot_banner",
            config=cfg,
            strict=True,
        )
    assert any("هنوز از طریق API" in w for w in result.warnings)


@pytest.mark.django_db
def test_studio_resolve_bot_endpoint_auth_and_shape(client, customer_user):
    client.force_login(customer_user)
    url = reverse("campaigns:catalog_resolve_bot")
    with patch("apps.campaigns.catalog.check_bot_eligibility") as mock_check:
        mock_check.return_value = MagicMock(
            to_json=lambda: {
                "ok": True,
                "username": "@vote",
                "eligibility": "eligible",
                "message_fa": "ok",
                "bot": {"title": "VoteBot"},
                "hard_block": False,
            }
        )
        response = client.get(url, {"username": "@vote"})
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["eligibility"] == "eligible"


@pytest.mark.django_db
def test_draft_preserves_bot_peer_checks(client, customer_user):
    from apps.campaigns.models import Campaign
    from apps.campaigns.studio import parse_targeting_payload

    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="bot draft",
        target_type="bots",
        wizard_version=2,
    )
    payload = {
        "bot_ids": "@vote\n@gif",
        "bot_eligibility_json": json.dumps(
            {"@vote": {"eligibility": "eligible", "message_fa": "ok", "bot": {"title": "V"}}},
            ensure_ascii=False,
        ),
    }
    cfg = parse_targeting_payload(payload, "bots")
    assert "@vote" in cfg["bot_ids"]
    # Browser-supplied eligibility is not authoritative and is not persisted.
    assert "@vote" not in cfg["bot_peer_checks"]


def test_short_official_username_and_fake_url():
    assert parse_bot_peer_input("@gif") == ("@gif", "@gif")
    assert parse_bot_peer_input("https://evil.invalid/t.me/vote") == (None, None)


@patch("apps.telegram_ads.services.bot_eligibility.TelegramAdsClient")
def test_empty_success_is_not_verified(mock_client):
    mock_client.return_value.resolve_target_bot.return_value = {}
    result = check_bot_eligibility("@vote", use_cache=False)
    assert result.eligibility == "unknown"
    assert not result.verified
