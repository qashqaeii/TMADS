import json
from unittest.mock import MagicMock

import pytest
from django.test import override_settings
from django.urls import reverse

from apps.ai import provider
from apps.ai.provider import AiError
from apps.campaigns.models import Campaign, TelegramAdvertisement


def test_arvan_endpoint_accepts_panel_base_and_complete_url():
    with override_settings(ARVAN_AI_BASE_URL="https://ai.divarfiling.ir/v1/"):
        assert provider.endpoint() == "https://ai.divarfiling.ir/v1/chat/completions"
    with override_settings(ARVAN_AI_BASE_URL="https://gateway.arvancloudai.ir/v1/chat/completions"):
        assert provider.endpoint() == "https://gateway.arvancloudai.ir/v1/chat/completions"


@pytest.mark.parametrize("url", [
    "http://gateway.arvancloudai.ir/v1",
    "https://localhost/v1",
    "https://127.0.0.1/v1",
    "https://user:pass@gateway.arvancloudai.ir/v1",
    "https://gateway.arvancloudai.ir/v1?token=secret",
    "https://gateway.arvancloudai.ir/v1#fragment",
])
def test_arvan_endpoint_rejects_unsafe_urls(url):
    with override_settings(ARVAN_AI_BASE_URL=url):
        assert provider.endpoint() == ""


def test_arvan_authorization_prefix_is_not_duplicated():
    with override_settings(ARVAN_AI_API_KEY="Apikey existing-key"):
        assert provider.authorization_header() == "apikey existing-key"


def test_ai_ui_visible_in_local_debug_without_credentials():
    with override_settings(
        DEBUG=True,
        APP_ENV="LOCAL",
        ARVAN_AI_ENABLED=False,
        ARVAN_AI_BASE_URL="",
        ARVAN_AI_API_KEY="",
    ):
        assert provider.available() is False
        assert provider.ui_visible() is True


def test_ai_ui_hidden_in_production_without_credentials():
    with override_settings(
        DEBUG=False,
        APP_ENV="PRODUCTION",
        ARVAN_AI_ENABLED=False,
        ARVAN_AI_BASE_URL="",
        ARVAN_AI_API_KEY="",
    ):
        assert provider.available() is False
        assert provider.ui_visible() is False


def test_arvan_provider_sends_selected_model_and_parses_usage(monkeypatch):
    captured = {}

    class Response:
        status_code = 200
        headers = {}

        @staticmethod
        def json():
            return {
                "model": "Gemini-2.5-Flash-lite",
                "choices": [{"message": {"content": json.dumps({"ok": True})}}],
                "usage": {"prompt_tokens": 23, "completion_tokens": 11},
            }

    class Client:
        def __init__(self, **kwargs):
            captured["client"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, headers, json):
            captured.update({"url": url, "headers": headers, "payload": json})
            return Response()

    monkeypatch.setattr(provider.httpx, "Client", Client)
    with override_settings(
        ARVAN_AI_ENABLED=True,
        ARVAN_AI_BASE_URL="https://ai.divarfiling.ir/v1",
        ARVAN_AI_API_KEY="secret-key",
        ARVAN_AI_MODEL="Gemini-2.5-Flash-lite",
        ARVAN_AI_TIMEOUT_SECONDS=10,
        ARVAN_AI_MAX_RETRIES=0,
        ARVAN_AI_MAX_TOKENS=900,
        ARVAN_AI_TEMPERATURE=0.2,
    ):
        result, input_tokens, output_tokens = provider.complete(
            "system", {"brief": "test"}, max_tokens=400, temperature=0.15
        )

    assert result == {"ok": True}
    assert (input_tokens, output_tokens) == (23, 11)
    assert captured["url"] == "https://ai.divarfiling.ir/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "apikey secret-key"
    assert captured["payload"]["model"] == "Gemini-2.5-Flash-lite"
    assert captured["payload"]["max_tokens"] == 400
    assert captured["payload"]["temperature"] == 0.15
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["client"]["follow_redirects"] is False


def test_arvan_provider_maps_auth_error_without_exposing_secret(monkeypatch):
    class Response:
        status_code = 401
        headers = {}

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(provider.httpx, "Client", Client)
    with override_settings(
        ARVAN_AI_ENABLED=True,
        ARVAN_AI_BASE_URL="https://ai.divarfiling.ir/v1",
        ARVAN_AI_API_KEY="secret-key",
        ARVAN_AI_MODEL="Gemini-2.5-Flash-lite",
    ):
        with pytest.raises(AiError, match="provider_auth") as exc:
            provider.complete("system", {"brief": "test"})
    assert "secret-key" not in str(exc.value)


@pytest.mark.django_db
def test_campaign_planner_sanitizes_context_and_validates_target_type(monkeypatch, customer_profile):
    from apps.ai import features

    campaign = Campaign.objects.create(customer=customer_profile, name="کمپین جدید", wizard_version=2)
    captured = {}

    def fake_run(customer, feature, system, context, validate, **kwargs):
        captured.update({"customer": customer, "feature": feature, "context": context, "kwargs": kwargs})
        return validate({
            "campaign_name": "معرفی محصول جدید",
            "target_type": "channels",
            "reason": "کانال‌های مرتبط مسیر شروع مناسب‌تری برای این هدف هستند.",
            "audience_summary": "مخاطبان علاقه‌مند به موضوع محصول",
            "creative_direction": "تمرکز بر مزیت اصلی و دعوت روشن به اقدام",
            "missing_information": ["موضوعات دقیق مخاطب"],
        }), False

    monkeypatch.setattr(features, "run", fake_run)
    plan, cached = features.plan_campaign(
        customer_profile,
        campaign,
        "معرفی نرم‌افزار مدیریت فروشگاه https://example.com",
        audience="مدیران فروشگاه",
        goal="دریافت مشتری بالقوه",
    )

    assert cached is False
    assert plan["target_type"] == "channels"
    assert plan["target_type_label"] == "کانال‌های تلگرام"
    assert captured["feature"] == "planner"
    assert "example.com" not in json.dumps(captured["context"], ensure_ascii=False)
    assert "destination" not in captured["context"]
    assert captured["kwargs"]["cache_ttl_seconds"] == 86_400


@pytest.mark.django_db
def test_campaign_planner_rejects_unsupported_target_type(monkeypatch, customer_profile):
    from apps.ai import features

    campaign = Campaign.objects.create(customer=customer_profile, name="کمپین جدید", wizard_version=2)

    def fake_run(customer, feature, system, context, validate, **kwargs):
        return validate({
            "campaign_name": "نام کمپین",
            "target_type": "invented_target",
            "reason": "دلیل",
            "audience_summary": "مخاطب",
            "creative_direction": "مسیر محتوا",
            "missing_information": [],
        }), False

    monkeypatch.setattr(features, "run", fake_run)
    with pytest.raises(AiError, match="invalid_output"):
        features.plan_campaign(customer_profile, campaign, "توضیح محصول")


@pytest.mark.django_db
def test_campaign_optimization_only_accepts_backend_allowed_actions(monkeypatch, customer_profile):
    from apps.ai import features
    from apps.campaigns.analytics import aggregate_campaign_metrics

    campaign = Campaign.objects.create(
        customer=customer_profile,
        name="کمپین آزمایشی",
        status=Campaign.Status.ACTIVE,
        target_type=Campaign.TargetType.CHANNELS,
        wizard_version=2,
    )
    TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id="ai-test-1")
    metrics = {
        "has_stats": True, "stats_stale": False, "has_impressions": True,
        "has_clicks": True, "has_actions": True, "has_ctr": True,
        "has_conversion": True, "impressions": 3000, "clicks": 8, "actions": 1,
        "ctr": 0.26, "conversion_rate": 12.5, "spent_ton": None,
        "remaining_ton": None, "currency": None, "action_type": "join",
    }
    monkeypatch.setattr("apps.campaigns.analytics.aggregate_campaign_metrics", lambda campaign: metrics)
    captured = {}

    def fake_run(customer, feature, system, context, validate, **kwargs):
        captured.update({"feature": feature, "context": context})
        return validate({
            "summary": "عملکرد فعلی برای تصمیم‌گیری اولیه سیگنال کافی دارد.",
            "recommendations": [
                {"action": "creative_test", "priority": "high", "reason": "نرخ کلیک پایین است و آزمایش متن می‌تواند مفید باشد."},
                {"action": "budget_review", "priority": "high", "reason": "بودجه نیاز به بررسی دارد."},
            ],
        }), False

    monkeypatch.setattr(features, "run", fake_run)
    result, cached = features.optimize_campaign(customer_profile, campaign)
    assert cached is False
    assert captured["feature"] == "optimization"
    assert "creative_test" in captured["context"]["allowed_actions"]
    assert "budget_review" not in captured["context"]["allowed_actions"]
    assert [item["id"] for item in result["recommendations"]] == ["creative_test"]


@pytest.mark.django_db
def test_campaign_planner_endpoint_is_explicit_and_step_scoped(client, customer_user, monkeypatch):
    from apps.campaigns import ai_views

    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="کمپین جدید",
        status=Campaign.Status.DRAFT,
        wizard_version=2,
        wizard_step=1,
    )
    monkeypatch.setattr(ai_views, "available", lambda: True)
    monkeypatch.setattr(
        ai_views,
        "plan_campaign",
        lambda *args, **kwargs: ({
            "campaign_name": "پیشنهاد",
            "target_type": "channels",
            "target_type_label": "کانال‌های تلگرام",
            "reason": "دلیل",
            "audience_summary": "مخاطب",
            "creative_direction": "مسیر محتوا",
            "missing_information": [],
        }, False),
    )
    client.login(username=customer_user.username, password="pass1234")
    response = client.post(
        reverse("campaigns:ai_plan", kwargs={"campaign_id": campaign.id}),
        {"brief": "معرفی محصول", "audience": "مخاطب", "goal": "آگاهی"},
    )
    assert response.status_code == 200
    assert response.json()["plan"]["target_type"] == "channels"
    campaign.wizard_step = 2
    campaign.save(update_fields=["wizard_step"])
    response = client.post(
        reverse("campaigns:ai_plan", kwargs={"campaign_id": campaign.id}),
        {"brief": "معرفی محصول"},
    )
    assert response.status_code == 409
