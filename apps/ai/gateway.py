"""Per-tenant cache, persistent call caps and strict output validation."""
import hashlib
import json
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import AiDay, AiRun
from .provider import AiError, available, complete

VERSION = "1"


def run(customer, feature, system, context, validate):
    if not available():
        raise AiError("disabled")
    encoded = json.dumps([VERSION, settings.ARVAN_AI_MODEL, feature, context], ensure_ascii=False, sort_keys=True)
    if len(encoded) > 12000:
        raise AiError("invalid_input")
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    today = timezone.localdate()
    with transaction.atomic():
        day, _ = AiDay.objects.get_or_create(day=today)
        AiDay.objects.select_for_update().get(pk=day.pk)
        rows = AiRun.objects.filter(day=today)
        same = rows.filter(customer=customer, feature=feature, fingerprint=fingerprint)
        cached = same.filter(state="ok").order_by("-created_at").first()
        if cached:
            return cached.result, True
        if same.filter(state="pending", created_at__gte=timezone.now()-timedelta(minutes=2)).exists():
            raise AiError("busy")
        if (rows.count() >= max(0, settings.ARVAN_AI_GLOBAL_DAILY_LIMIT)
                or rows.filter(customer=customer).count() >= max(0, settings.ARVAN_AI_USER_DAILY_LIMIT)):
            raise AiError("quota")
        if rows.filter(customer=customer, created_at__gte=timezone.now()-timedelta(seconds=5)).exists():
            raise AiError("busy")
        job = AiRun.objects.create(customer=customer, day=today, feature=feature, fingerprint=fingerprint)
    try:
        raw, inp, out = complete(system, context)
        AiRun.objects.filter(pk=job.pk).update(input_tokens=inp, output_tokens=out)
        result = validate(raw)
    except AiError as exc:
        AiRun.objects.filter(pk=job.pk).update(state="failed", error=str(exc)[:32])
        raise
    AiRun.objects.filter(pk=job.pk).update(state="ok", result=result)
    return result, False
