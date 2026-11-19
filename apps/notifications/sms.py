"""Durable transactional outbox. External calls never run in payment transactions."""
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import SmsContact, SmsOutbox
from .faraz import configured, send_pattern

EVENT_PURPOSES = {"wallet_credit", "budget_low", "campaign_status"}


def enqueue_sms(customer, purpose, event_key, attributes):
    if not settings.SMS_ENABLED or purpose not in EVENT_PURPOSES:
        return None
    if not configured(purpose) or customer.is_suspended:
        return None
    contact = SmsContact.objects.filter(customer=customer, enabled=True).first()
    if not contact:
        return None
    row, _ = SmsOutbox.objects.get_or_create(customer=customer, event_key=event_key,
        defaults={"purpose": purpose, "phone": contact.phone, "attributes": attributes})
    return row


def dispatch_one(message_id):
    with transaction.atomic():
        row = SmsOutbox.objects.select_for_update().select_related("customer").filter(pk=message_id).first()
        if not row or row.status != SmsOutbox.Status.QUEUED:
            return
        if (not configured(row.purpose) or row.customer.is_suspended
                or not SmsContact.objects.filter(customer=row.customer, phone=row.phone, enabled=True).exists()
                or row.created_at < timezone.now() - timedelta(hours=24)):
            row.status = SmsOutbox.Status.SKIPPED
            row.error_code = "ineligible_or_expired"
            row.save(update_fields=["status", "error_code", "updated_at"])
            return
        row.status = SmsOutbox.Status.SENDING
        row.save(update_fields=["status", "updated_at"])
    result = send_pattern(row.phone, row.purpose, row.attributes)
    SmsOutbox.objects.filter(pk=row.pk, status=SmsOutbox.Status.SENDING).update(
        status=result.state, provider_id=result.provider_id, error_code=result.error, updated_at=timezone.now())


def dispatch_pending(limit=50):
    SmsOutbox.objects.filter(status=SmsOutbox.Status.SENDING,
        updated_at__lt=timezone.now()-timedelta(minutes=10)).update(
            status=SmsOutbox.Status.UNKNOWN, error_code="worker_interrupted", updated_at=timezone.now())
    ids = list(SmsOutbox.objects.filter(status=SmsOutbox.Status.QUEUED).order_by("created_at").values_list("pk", flat=True)[:limit])
    for pk in ids:
        dispatch_one(pk)
    return len(ids)
