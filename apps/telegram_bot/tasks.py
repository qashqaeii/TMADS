from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .handler import process_update_payload
from .models import TelegramOutbox, TelegramUpdateLog
from .security import callback_already_processed
from .services.delivery import send_outbox_row

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=3)
def process_telegram_update(self, update_log_id: str) -> None:
    row = TelegramUpdateLog.objects.filter(pk=update_log_id).first()
    if not row or row.status in {TelegramUpdateLog.Status.DONE, TelegramUpdateLog.Status.DUPLICATE}:
        return
    row.status = TelegramUpdateLog.Status.PROCESSING
    row.save(update_fields=["status", "updated_at"])
    payload = row.payload or {}
    callback = (payload.get("callback_query") or {})
    cb_id = callback.get("id")
    if cb_id and callback_already_processed(str(cb_id)):
        row.status = TelegramUpdateLog.Status.DUPLICATE
        row.processed_at = timezone.now()
        row.save(update_fields=["status", "processed_at", "updated_at"])
        return
    try:
        process_update_payload(payload)
        row.status = TelegramUpdateLog.Status.DONE
        row.processed_at = timezone.now()
        row.error_message = ""
        row.save(update_fields=["status", "processed_at", "error_message", "updated_at"])
    except Exception as exc:
        row.status = TelegramUpdateLog.Status.FAILED
        row.error_message = str(exc)[:2000]
        row.save(update_fields=["status", "error_message", "updated_at"])
        raise self.retry(exc=exc) from exc


@shared_task
def flush_telegram_outbox(batch_size: int = 40) -> int:
    sent = 0
    qs = TelegramOutbox.objects.filter(status=TelegramOutbox.Status.QUEUED).order_by("created_at")[:batch_size]
    for row in qs:
        if send_outbox_row(row):
            sent += 1
    return sent


@shared_task
def deliver_notification(notification_id: str) -> int:
    from apps.notifications.models import Notification
    from .services.delivery import enqueue_notification_for_customer

    note = Notification.objects.filter(pk=notification_id).first()
    if not note:
        return 0
    return enqueue_notification_for_customer(note)