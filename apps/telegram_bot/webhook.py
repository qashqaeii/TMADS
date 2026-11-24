from __future__ import annotations

import json
import logging

from django.http import HttpResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .config import bot_runtime_enabled, get_bot_config
from .models import TelegramUpdateLog
from .security import verify_webhook_secret
from .tasks import process_telegram_update

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    if not bot_runtime_enabled():
        return HttpResponse(status=503)
    secret_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not verify_webhook_secret(secret_header):
        return HttpResponseForbidden("invalid webhook secret")
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponse(status=400)

    update_id = payload.get("update_id")
    if update_id is None:
        return HttpResponse(status=400)

    user_id = None
    if payload.get("message", {}).get("from"):
        user_id = payload["message"]["from"].get("id")
    elif payload.get("callback_query", {}).get("from"):
        user_id = payload["callback_query"]["from"].get("id")

    update_type = "callback_query" if "callback_query" in payload else "message" if "message" in payload else "other"
    log, created = TelegramUpdateLog.objects.get_or_create(
        update_id=int(update_id),
        defaults={
            "payload": payload,
            "status": TelegramUpdateLog.Status.QUEUED,
            "telegram_user_id": user_id,
            "update_type": update_type,
        },
    )
    if not created:
        if log.status in {
            TelegramUpdateLog.Status.FAILED,
            TelegramUpdateLog.Status.QUEUED,
        }:
            process_telegram_update.delay(str(log.pk))
        elif log.status == TelegramUpdateLog.Status.DONE:
            log.status = TelegramUpdateLog.Status.DUPLICATE
            log.save(update_fields=["status", "updated_at"])
        return HttpResponse(status=200)

    process_telegram_update.delay(str(log.pk))
    return HttpResponse(status=200)