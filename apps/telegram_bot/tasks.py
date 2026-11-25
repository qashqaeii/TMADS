from __future__ import annotations

import logging

from celery import shared_task
from django.utils import timezone

from .handler import process_update_payload
from .models import TelegramOutbox, TelegramUpdateLog
from .services.delivery import send_outbox_row, recover_stuck_outbox_rows

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=3)
def process_telegram_update(self, update_log_id: str) -> None:
    # Claim each update atomically, including retries from duplicate webhooks.
    claimed = TelegramUpdateLog.objects.filter(
        pk=update_log_id,
        status__in=[TelegramUpdateLog.Status.QUEUED, TelegramUpdateLog.Status.FAILED],
    ).update(status=TelegramUpdateLog.Status.PROCESSING, updated_at=timezone.now())
    if not claimed:
        return
    row = TelegramUpdateLog.objects.get(pk=update_log_id)
    payload = row.payload or {}
    try:
        process_update_payload(payload)
        row.status = TelegramUpdateLog.Status.DONE
        row.processed_at = timezone.now()
        row.error_message = ""
        # Avoid retaining one-time /start credentials after processing.
        row.payload = {}
        row.save(update_fields=["status", "processed_at", "error_message", "payload", "updated_at"])
    except Exception as exc:
        row.status = TelegramUpdateLog.Status.FAILED
        row.error_message = str(exc)[:2000]
        row.save(update_fields=["status", "error_message", "updated_at"])
        raise self.retry(exc=exc) from exc


@shared_task
def flush_telegram_outbox(batch_size: int = 40) -> int:
    recover_stuck_outbox_rows()
    sent = 0
    from django.db.models import Q

    qs = (
        TelegramOutbox.objects.filter(
            Q(status=TelegramOutbox.Status.QUEUED)
            | Q(status=TelegramOutbox.Status.FAILED, attempt_count__lt=8)
        )
        .order_by("created_at")[:batch_size]
    )
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