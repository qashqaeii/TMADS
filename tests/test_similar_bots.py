"""Similar Bots — catalog recommendations gated by official getTargetBot."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.accounts.models import User
from apps.campaigns.models import Campaign, CampaignTargeting
from apps.telegram_ads.models import TargetBotCatalogEntry
from apps.telegram_ads.services.bot_eligibility import BotEligibilityResult
from apps.telegram_ads.services.bot_recommendation import (
    CatalogBotRecommendationAdapter,
    MIN_RECOMMENDATION_SCORE,
    score_catalog_entry,
    load_seed_context,
)
from apps.telegram_ads.services.similar_bots import SimilarBotsService


@pytest.fixture(autouse=True)
def clear_caches():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def catalog_seed(db):
    seed = TargetBotCatalogEntry.objects.create(
        username="@SeedVPNBot",
        title="Seed VPN",
        category="vpn",
        language_codes=["fa"],
        tags=["vpn", "proxy"],
        related_usernames=["@PeerVPNBot"],
        priority=10,
        is_active=True,
    )
    peer = TargetBotCatalogEntry.objects.create(
        username="@PeerVPNBot",
        title="Peer VPN",
        category="vpn",
        language_codes=["fa"],
        tags=["vpn"],
        photo_url="https://cdn.example.com/peer.jpg",
        monthly_users=12000,
        priority=5,
        is_active=True,
    )
    other = TargetBotCatalogEntry.objects.create(
        username="@MusicBotX",
        title="Music",
        category="music",
        language_codes=["en"],
        tags=["music"],
        priority=1,
        is_active=True,
    )
    inactive = TargetBotCatalogEntry.objects.create(
        username="@DeadVPNBot",
        title="Dead",
        category="vpn",
        language_codes=["fa"],
        tags=["vpn"],
        is_active=False,
    )
    return {"seed": seed, "peer": peer, "other": other, "inactive": inactive}


def _eligible(username: str, bot_id: int = 1001) -> BotEligibilityResult:
    bare = username.lstrip("@")
    return BotEligibilityResult(
        ok=True,
        query=username,
        username=f"@{bare}" if not username.startswith("@") else username,
        eligibility="eligible",
        message_fa="ok",
        hard_block=False,
        verified=True,
        bot={"bot_id": bot_id, "title": bare, "username": bare},
    )


def test_score_requires_meaningful_similarity(catalog_seed):
    seed_ctx = load_seed_context("@SeedVPNBot")
    music = catalog_seed["other"]
    cand = score_catalog_entry(music, seed=seed_ctx, customer_history=set(), cotarget={})
    assert cand is None or cand.score < MIN_RECOMMENDATION_SCORE or cand.username != "@MusicBotX"


def test_catalog_adapter_prefers_related_and_same_category(catalog_seed):
    adapter = CatalogBotRecommendationAdapter()
    rows = adapter.recommend(
        seed="@SeedVPNBot",
        exclude=set(),
        customer_id=None,
        limit=12,
    )
    usernames = [r.username.casefold() for r in rows]
    assert "@peervpnbot" in usernames
    assert "@musicbotx" not in usernames
    assert "@seedvpnbot" not in usernames
    assert "@deadvpnbot" not in usernames


def test_infer_category_from_seed_title_when_not_in_catalog(catalog_seed):
    adapter = CatalogBotRecommendationAdapter()
    rows = adapter.recommend(
        seed="@HyperVpnRobot",
        exclude=set(),
        customer_id=None,
        limit=12,
        seed_title="Hyper VPN",
    )
    usernames = [r.username.casefold() for r in rows]
    assert "@peervpnbot" in usernames
    assert "@musicbotx" not in usernames


def test_catalog_adapter_excludes_duplicates(catalog_seed):
    adapter = CatalogBotRecommendationAdapter()
    rows = adapter.recommend(
        seed="@SeedVPNBot",
        exclude={"@PeerVPNBot"},
        customer_id=None,
        limit=12,
    )
    assert all(r.username.casefold() != "@peervpnbot" for r in rows)


def test_xss_stripped_from_catalog_titles(db):
    TargetBotCatalogEntry.objects.create(
        username="@CleanBot",
        title='Safe',
        category="tools",
        related_usernames=[],
        is_active=True,
    )
    TargetBotCatalogEntry.objects.create(
        username="@XssBot",
        title='<img src=x onerror=alert(1)>Evil',
        category="tools",
        tags=["tools"],
        related_usernames=["@CleanBot"],
        photo_url='javascript:alert(1)',
        is_active=True,
    )
    # Make CleanBot related to Xss for scoring path via reverse related on Xss
    TargetBotCatalogEntry.objects.filter(username="@CleanBot").update(
        related_usernames=["@XssBot"],
        tags=["tools"],
    )
    adapter = CatalogBotRecommendationAdapter()
    rows = adapter.recommend(seed="@CleanBot", exclude=set(), customer_id=None, limit=12)
    assert rows
    hit = next(r for r in rows if r.username.casefold() == "@xssbot")
    assert "<" not in hit.title
    assert "Evil" in hit.title
    assert hit.photo_url == ""


@patch("apps.telegram_ads.services.similar_bots.check_bot_eligibility")
def test_service_returns_only_eligible_verified(mock_check, catalog_seed, customer_profile):
    def fake_check(value, *, use_cache=True, account_scope=None):
        at = value if str(value).startswith("@") else f"@{value}"
        if at.casefold() == "@seedvpnbot":
            return _eligible("@SeedVPNBot", 1)
        if at.casefold() == "@peervpnbot":
            return _eligible("@PeerVPNBot", 2)
        return BotEligibilityResult(
            ok=False,
            query=at,
            username=at,
            eligibility="insufficient_audience",
            message_fa="small",
            hard_block=True,
            verified=True,
        )

    mock_check.side_effect = fake_check
    result = SimilarBotsService().get_similar("@SeedVPNBot", customer=customer_profile, use_cache=False)
    assert result.ok
    assert result.seed == "@SeedVPNBot"
    assert len(result.items) == 1
    assert result.items[0].username == "@PeerVPNBot"
    assert result.items[0].bot_id == 2
    assert result.items[0].monthly_users == 12000
    assert "val" not in result.to_json()["items"][0]
    assert "cb_item" not in result.to_json()["items"][0]


@patch("apps.telegram_ads.services.similar_bots.check_bot_eligibility")
def test_service_empty_when_no_catalog_matches(mock_check, db, customer_profile):
    mock_check.return_value = _eligible("@LonelyBot", 9)
    result = SimilarBotsService().get_similar("@LonelyBot", customer=customer_profile, use_cache=False)
    assert result.ok
    assert result.items == []
    assert result.reason in {"no_matches", "adapter_error"} or result.message_fa


@patch("apps.telegram_ads.services.similar_bots.check_bot_eligibility")
def test_service_seed_api_unavailable_is_not_success_suggestions(mock_check, catalog_seed, customer_profile):
    mock_check.return_value = BotEligibilityResult(
        ok=False,
        query="@SeedVPNBot",
        username="@SeedVPNBot",
        eligibility="api_unavailable",
        message_fa="down",
        hard_block=False,
        verified=False,
    )
    result = SimilarBotsService().get_similar("@SeedVPNBot", customer=customer_profile, use_cache=False)
    assert result.ok
    assert result.items == []
    assert result.reason == "seed_unverified"


@patch("apps.telegram_ads.services.similar_bots.check_bot_eligibility")
def test_service_invalid_seed(mock_check, customer_profile):
    result = SimilarBotsService().get_similar("!!!", customer=customer_profile, use_cache=False)
    assert result.ok is False
    assert result.reason == "invalid_seed"
    mock_check.assert_not_called()


@patch("apps.telegram_ads.services.similar_bots.check_bot_eligibility")
def test_cache_hit_avoids_repeat_work(mock_check, catalog_seed, customer_profile):
    mock_check.side_effect = lambda value, **kwargs: _eligible(value, 42)
    svc = SimilarBotsService()
    first = svc.get_similar("@SeedVPNBot", customer=customer_profile, use_cache=True)
    calls_after_first = mock_check.call_count
    second = svc.get_similar("@SeedVPNBot", customer=customer_profile, use_cache=True)
    assert first.items and second.items
    assert mock_check.call_count == calls_after_first


@patch("apps.telegram_ads.services.similar_bots.check_bot_eligibility")
def test_customer_history_does_not_leak_other_customer(mock_check, catalog_seed, customer_profile, db):
    other_user = User.objects.create_user(username="cust_other", password="pass1234", role=User.Role.CUSTOMER)
    other = other_user.customer_profile
    campaign = Campaign.objects.create(
        customer=other,
        name="other",
        target_type=Campaign.TargetType.BOTS,
        status=Campaign.Status.ACTIVE,
    )
    CampaignTargeting.objects.create(
        campaign=campaign,
        config={"bot_ids": ["@SeedVPNBot", "@MusicBotX"]},
    )

    mock_check.side_effect = lambda value, **kwargs: _eligible(value, 7)
    # Viewer is customer_profile, not `other` — music should not surface via private history.
    result = SimilarBotsService().get_similar("@SeedVPNBot", customer=customer_profile, use_cache=False)
    usernames = {i.username.casefold() for i in result.items}
    assert "@musicbotx" not in usernames


def test_endpoint_requires_auth(client):
    url = reverse("campaigns:bots_similar")
    res = client.post(url, {"seed": "@SeedVPNBot"})
    assert res.status_code in {302, 401, 403}


@patch("apps.telegram_ads.services.similar_bots.check_bot_eligibility")
def test_endpoint_happy_path(mock_check, client, customer_user, catalog_seed):
    mock_check.side_effect = lambda value, **kwargs: _eligible(value, 55)
    client.force_login(customer_user)
    url = reverse("campaigns:bots_similar")
    res = client.post(url, {"seed": "@SeedVPNBot", "exclude": "[]", "limit": "12"})
    assert res.status_code == 200
    payload = res.json()
    assert payload["ok"] is True
    assert payload["seed"] == "@SeedVPNBot"
    assert payload["items"]
    assert all(i.get("eligibility") == "eligible" and i.get("verified") for i in payload["items"])
    assert all("cb_item" not in i and "val" not in i for i in payload["items"])


@patch("apps.campaigns.views._catalog_rate_limited", return_value=True)
def test_endpoint_rate_limit(mock_rate, client, customer_user):
    client.force_login(customer_user)
    url = reverse("campaigns:bots_similar")
    res = client.post(url, {"seed": "@SeedVPNBot"})
    assert res.status_code == 429
    assert res.json()["reason"] == "rate_limited"


def test_feature_flag_disables_endpoint(client, customer_user, settings):
    settings.SIMILAR_BOTS_ENABLED = False
    client.force_login(customer_user)
    url = reverse("campaigns:bots_similar")
    res = client.post(url, {"seed": "@SeedVPNBot"})
    assert res.status_code == 200
    body = res.json()
    assert body["feature_enabled"] is False
    assert body["items"] == []


@patch("apps.telegram_ads.services.similar_bots.check_bot_eligibility")
def test_exclude_and_limit_cap(mock_check, catalog_seed, customer_profile, db):
    # Add more vpn peers
    for i in range(8):
        TargetBotCatalogEntry.objects.create(
            username=f"@ExtraVPN{i}",
            title=f"Extra {i}",
            category="vpn",
            language_codes=["fa"],
            tags=["vpn"],
            related_usernames=["@SeedVPNBot"],
            priority=3,
            is_active=True,
        )
    mock_check.side_effect = lambda value, **kwargs: _eligible(value, abs(hash(str(value))) % 100000 + 1)
    result = SimilarBotsService().get_similar(
        "@SeedVPNBot",
        customer=customer_profile,
        exclude=["@PeerVPNBot", "@ExtraVPN0"],
        limit=3,
        use_cache=False,
    )
    assert len(result.items) <= 3
    keys = {i.username.casefold() for i in result.items}
    assert "@peervpnbot" not in keys
    assert "@extravpn0" not in keys
    assert "@seedvpnbot" not in keys
