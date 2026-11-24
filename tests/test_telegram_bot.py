from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.telegram_bot.config import get_bot_config
from apps.telegram_bot.handler import process_update_payload
from apps.telegram_bot.models import TelegramUpdateLog, TelegramUserLink
from apps.telegram_bot.security import digest_token, generate_link_token
from apps.telegram_bot.services.link import consume_link_token, create_link_token
from apps.telegram_bot.tasks import process_telegram_update


@pytest.fixture
def bot_settings(settings):
    settings.GRAMADS_BOT_TOKEN = "000000000:TEST-TOKEN-FOR-CI"
    settings.GRAMADS_BOT_WEBHOOK_SECRET = "test-webhook-secret"
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True
    settings.PUBLIC_SITE_URL = "https://gramads.example"
    cfg = get_bot_config()
    cfg.enabled = True
    cfg.save(update_fields=["enabled", "updated_at"])
    return settings


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    sent = {}

    def send_message(chat_id, text, **kwargs):
        msg = MagicMock()
        msg.message_id = sent.get("message_id", 101)
        sent["chat_id"] = chat_id
        sent["text"] = text
        sent["message_id"] = msg.message_id
        return msg

    def edit_message_text(text, chat_id, message_id, **kwargs):
        sent["text"] = text
        sent["edit"] = True

    bot.send_message.side_effect = send_message
    bot.edit_message_text.side_effect = edit_message_text
    bot.answer_callback_query.return_value = True
    with patch("apps.telegram_bot.handler.get_bot", return_value=bot):
        with patch("apps.telegram_bot.bot.get_bot", return_value=bot):
            yield bot, sent


@pytest.mark.django_db
def test_link_token_flow(customer_profile, bot_settings, mock_bot):
    raw = create_link_token(customer_profile)
    link = consume_link_token(raw, telegram_user_id=9001, chat_id=9001, telegram_username="demo")
    assert link.is_active
    assert TelegramUserLink.objects.filter(customer=customer_profile, is_active=True).count() == 1


@pytest.mark.django_db
def test_start_command_renders_dashboard(customer_profile, bot_settings, mock_bot):
    mock_bot_obj, sent = mock_bot
    raw = create_link_token(customer_profile)
    consume_link_token(raw, telegram_user_id=42, chat_id=42)
    process_update_payload(
        {
            "update_id": 1,
            "message": {
                "message_id": 10,
                "chat": {"id": 42, "type": "private"},
                "from": {"id": 42, "username": "u"},
                "text": "/start",
            },
        }
    )
    assert "داشبورد" in sent.get("text", "")


@pytest.mark.django_db
def test_webhook_queues_and_processes(customer_user, customer_profile, bot_settings, mock_bot, client: Client):
    client.force_login(customer_user)
    raw = create_link_token(customer_profile)
    consume_link_token(raw, telegram_user_id=77, chat_id=77)

    payload = {
        "update_id": 555,
        "callback_query": {
            "id": "cb1",
            "from": {"id": 77},
            "message": {"message_id": 12, "chat": {"id": 77}},
            "data": "go:c:wallet",
        },
    }
    response = client.post(
        reverse("telegram_bot:webhook"),
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="test-webhook-secret",
    )
    assert response.status_code == 200
    log = TelegramUpdateLog.objects.get(update_id=555)
    process_telegram_update(str(log.pk))
    assert log.status == TelegramUpdateLog.Status.DONE


@pytest.mark.django_db
def test_webhook_rejects_bad_secret(bot_settings, client: Client):
    response = client.post(
        reverse("telegram_bot:webhook"),
        data="{}",
        content_type="application/json",
        HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_duplicate_update_idempotent(bot_settings, client: Client):
    payload = {"update_id": 999, "message": {"message_id": 1, "chat": {"id": 1}, "from": {"id": 1}, "text": "/start"}}
    url = reverse("telegram_bot:webhook")
    headers = {"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": "test-webhook-secret"}
    r1 = client.post(url, data=json.dumps(payload), content_type="application/json", **headers)
    r2 = client.post(url, data=json.dumps(payload), content_type="application/json", **headers)
    assert r1.status_code == 200 and r2.status_code == 200
    assert TelegramUpdateLog.objects.filter(update_id=999).count() == 1


@pytest.mark.django_db
def test_cross_tenant_campaign_context(customer_user, db, bot_settings, mock_bot):
    from apps.accounts.models import User

    other = User.objects.create_user(username="cust2x", password="pass1234", role=User.Role.CUSTOMER)
    other_profile = other.customer_profile
    consume_link_token(create_link_token(customer_user.customer_profile), telegram_user_id=500, chat_id=500)

    from apps.campaigns.models import Campaign
    from apps.telegram_bot.models import TelegramMenuSession

    foreign = Campaign.objects.create(customer=other_profile, name="secret", budget_irr=100_000)
    session = TelegramMenuSession.objects.create(
        telegram_user_id=500,
        chat_id=500,
        context={"cmp_items": [str(foreign.pk)]},
        nav_stack=["c:cmp:v:0"],
    )
    process_update_payload(
        {
            "update_id": 2,
            "callback_query": {
                "id": "cb2",
                "from": {"id": 500},
                "message": {"message_id": 20, "chat": {"id": 500}},
                "data": "go:c:cmp:v:0",
            },
        }
    )
    _, sent = mock_bot
    assert "یافت نشد" in sent.get("text", "")