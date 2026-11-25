from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.utils import timezone

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
    if len(request.body) > 262144:
        return HttpResponse(status=413)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponse(status=400)
    if not isinstance(payload, dict) or type(payload.get("update_id")) is not int or payload["update_id"] < 0:
        return HttpResponse(status=400)
    update_id = payload["update_id"]
    message = payload.get("message") or {}
    callback = payload.get("callback_query") or {}
    if not isinstance(message, dict) or not isinstance(callback, dict):
        return HttpResponse(status=400)
    user_id = None
    if isinstance(message.get("from"), dict):
        user_id = message["from"].get("id")
    elif isinstance(callback.get("from"), dict):
        user_id = callback["from"].get("id")

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
    if not created and log.status == TelegramUpdateLog.Status.PROCESSING:
        if log.updated_at < timezone.now() - timedelta(minutes=5):
            updated = TelegramUpdateLog.objects.filter(
                pk=log.pk, status=TelegramUpdateLog.Status.PROCESSING,
                updated_at=log.updated_at,
            ).update(status=TelegramUpdateLog.Status.QUEUED, updated_at=timezone.now())
            if not updated:
                return HttpResponse(status=200)
        else:
            return HttpResponse(status=200)
    elif not created and log.status not in {
        TelegramUpdateLog.Status.FAILED, TelegramUpdateLog.Status.QUEUED,
    }:
        return HttpResponse(status=200)
    try:
        process_telegram_update.delay(str(log.pk))
    except Exception:
        logger.exception("Unable to enqueue Telegram update")
        return HttpResponse(status=503)
    return HttpResponse(status=200)