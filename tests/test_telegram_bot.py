from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.telegram_bot.config import get_bot_config
from apps.telegram_bot.handler import process_update_payload
from apps.telegram_bot.models import TelegramUpdateLog, TelegramUserLink
from apps.telegram_bot.formatters import escape_html
from apps.telegram_bot.security import callback_is_processed, record_callback_processed
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
    patches = [
        "apps.telegram_bot.handler.get_bot",
        "apps.telegram_bot.bot.get_bot",
        "apps.telegram_bot.chat_guard.get_bot",
        "apps.telegram_bot.services.delivery.get_bot",
    ]
    with patch(patches[0], return_value=bot), patch(patches[1], return_value=bot), patch(
        patches[2], return_value=bot
    ), patch(patches[3], return_value=bot):
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
                "message": {"message_id": 20, "chat": {"id": 500, "type": "private"}},
                "data": "go:c:cmp:v:0",
            },
        }
    )
    _, sent = mock_bot
    assert "یافت نشد" in sent.get("text", "")


@pytest.mark.django_db
def test_group_chat_does_not_show_dashboard(customer_profile, bot_settings, mock_bot):
    consume_link_token(create_link_token(customer_profile), telegram_user_id=88, chat_id=-100)
    _, sent = mock_bot
    process_update_payload(
        {
            "update_id": 3,
            "message": {
                "message_id": 1,
                "chat": {"id": -100, "type": "group"},
                "from": {"id": 88, "username": "u"},
                "text": "/start",
            },
        }
    )
    assert sent.get("text")
    assert "داشبورد" not in sent.get("text", "")
    assert "خصوصی" in sent.get("text", "")


@pytest.mark.django_db
def test_guest_link_button_uses_go_prefix(bot_settings, mock_bot):
    _, sent = mock_bot
    process_update_payload(
        {
            "update_id": 4,
            "callback_query": {
                "id": "cb-link",
                "from": {"id": 1},
                "message": {"message_id": 5, "chat": {"id": 1, "type": "private"}},
                "data": "go:c:guest:link",
            },
        }
    )
    assert "اتصال حساب" in sent.get("text", "")


@pytest.mark.django_db
def test_callback_retry_after_failure_without_premature_dedup(customer_profile, bot_settings, mock_bot):
    consume_link_token(create_link_token(customer_profile), telegram_user_id=91, chat_id=91)
    assert not callback_is_processed("cb-retry")
    with patch("apps.telegram_bot.handler.build_screen", side_effect=RuntimeError("boom")):
        with pytest.raises(RuntimeError):
            process_update_payload(
                {
                    "update_id": 5,
                    "callback_query": {
                        "id": "cb-retry",
                        "from": {"id": 91},
                        "message": {"message_id": 7, "chat": {"id": 91, "type": "private"}},
                        "data": "go:c:wallet",
                    },
                }
            )
    assert not callback_is_processed("cb-retry")
    process_update_payload(
        {
            "update_id": 6,
            "callback_query": {
                "id": "cb-retry",
                "from": {"id": 91},
                "message": {"message_id": 7, "chat": {"id": 91, "type": "private"}},
                "data": "go:c:wallet",
            },
        }
    )
    assert callback_is_processed("cb-retry")


@pytest.mark.django_db
def test_html_escape_notification_body(customer_profile, bot_settings):
    from apps.notifications.models import Notification
    from apps.telegram_bot.services.delivery import enqueue_notification_for_customer

    consume_link_token(create_link_token(customer_profile), telegram_user_id=55, chat_id=55)
    note = Notification.objects.create(
        customer=customer_profile,
        title="<script>alert(1)</script>",
        body="مبلغ <b>خطر</b> & تست",
    )
    enqueue_notification_for_customer(note)
    from apps.telegram_bot.models import TelegramOutbox

    row = TelegramOutbox.objects.get()
    assert "<script>" not in row.body
    assert escape_html("<b>") in row.body or "&lt;b&gt;" in row.body


@pytest.mark.django_db
def test_webhook_requeues_failed_update(bot_settings, client: Client):
    payload = {
        "update_id": 12345,
        "message": {"message_id": 1, "chat": {"id": 2, "type": "private"}, "from": {"id": 2}, "text": "/start"},
    }
    url = reverse("telegram_bot:webhook")
    headers = {"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": "test-webhook-secret"}
    client.post(url, data=json.dumps(payload), content_type="application/json", **headers)
    log = TelegramUpdateLog.objects.get(update_id=12345)
    log.status = TelegramUpdateLog.Status.FAILED
    log.save(update_fields=["status", "updated_at"])
    with patch("apps.telegram_bot.webhook.process_telegram_update.delay") as delay:
        client.post(url, data=json.dumps(payload), content_type="application/json", **headers)
        delay.assert_called_once_with(str(log.pk))


@pytest.mark.django_db
def test_outbox_retries_failed_row(customer_profile, bot_settings, mock_bot):
    mock_bot  # ensure get_bot is patched
    from apps.telegram_bot.models import TelegramOutbox
    from apps.telegram_bot.services.delivery import send_outbox_row

    link = consume_link_token(create_link_token(customer_profile), telegram_user_id=66, chat_id=66)
    row = TelegramOutbox.objects.create(
        link=link,
        telegram_user_id=66,
        chat_id=66,
        body="تست",
        dedupe_key="test:1",
        status=TelegramOutbox.Status.FAILED,
        attempt_count=1,
    )
    assert send_outbox_row(row) is True
    row.refresh_from_db()
    assert row.status == TelegramOutbox.Status.SENT

@pytest.mark.django_db
def test_render_transport_error_remains_retryable(customer_profile, bot_settings, mock_bot):
    consume_link_token(create_link_token(customer_profile), telegram_user_id=8101, chat_id=8101)
    bot, _ = mock_bot
    bot.edit_message_text.side_effect = RuntimeError("network unavailable")
    payload = {"callback_query": {
        "id": "retry-render-8101", "from": {"id": 8101},
        "message": {"message_id": 20, "chat": {"id": 8101, "type": "private"}},
        "data": "go:c:wallet",
    }}
    with pytest.raises(RuntimeError, match="network unavailable"):
        process_update_payload(payload)
    assert not callback_is_processed("retry-render-8101")
    bot.edit_message_text.side_effect = None
    process_update_payload(payload)
    assert callback_is_processed("retry-render-8101")


@pytest.mark.django_db
def test_stale_menu_recreated(customer_profile, bot_settings, mock_bot):
    consume_link_token(create_link_token(customer_profile), telegram_user_id=8102, chat_id=8102)
    bot, _ = mock_bot
    bot.edit_message_text.side_effect = RuntimeError("message to edit not found")
    process_update_payload({"callback_query": {
        "id": "stale-menu-8102", "from": {"id": 8102},
        "message": {"message_id": 20, "chat": {"id": 8102, "type": "private"}},
        "data": "go:c:wallet",
    }})
    assert bot.send_message.called
    assert callback_is_processed("stale-menu-8102")


@pytest.mark.django_db
def test_outbox_claim_prevents_duplicate_send(customer_profile, bot_settings, mock_bot):
    from apps.telegram_bot.models import TelegramOutbox
    from apps.telegram_bot.services.delivery import send_outbox_row
    link = consume_link_token(create_link_token(customer_profile), telegram_user_id=8103, chat_id=8103)
    row = TelegramOutbox.objects.create(
        link=link, telegram_user_id=8103, chat_id=8103,
        body="یک اعلان", dedupe_key="delivery-8103",
    )
    bot, _ = mock_bot
    assert send_outbox_row(row) is True
    assert send_outbox_row(row) is False
    assert bot.send_message.call_count == 1


@pytest.mark.django_db
def test_disconnect_disables_staff_link(customer_profile, bot_settings):
    from apps.accounts.models import User
    from apps.telegram_bot.models import TelegramStaffLink
    from apps.telegram_bot.services.link import revoke_link
    user = customer_profile.user
    user.role = User.Role.ADMIN
    user.save(update_fields=["role"])
    link = consume_link_token(create_link_token(customer_profile), telegram_user_id=8104, chat_id=8104)
    assert TelegramStaffLink.objects.filter(telegram_user_id=8104, is_active=True).exists()
    revoke_link(link, reason="explicit disconnect")
    assert not TelegramStaffLink.objects.filter(telegram_user_id=8104, is_active=True).exists()


@pytest.mark.django_db
def test_processing_update_cannot_execute_twice(bot_settings):
    log = TelegramUpdateLog.objects.create(
        update_id=8810, payload={"message": {}},
        status=TelegramUpdateLog.Status.PROCESSING,
    )
    with patch("apps.telegram_bot.tasks.process_update_payload") as process:
        process_telegram_update(str(log.pk))
        process.assert_not_called()


@pytest.mark.django_db
def test_webhook_rejects_invalid_update_types(bot_settings, client):
    url = reverse("telegram_bot:webhook")
    headers = {"HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN": "test-webhook-secret"}
    for payload in ('["invalid"]', '{"update_id": true}', '{"update_id": "5"}', '{"update_id": 8, "message": "bad"}'):
        response = client.post(url, data=payload, content_type="application/json", **headers)
        assert response.status_code == 400
