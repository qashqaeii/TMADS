"""Per-tenant AI cache, serialized daily caps and request deduplication."""
import hashlib
import json
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import AiDay, AiRun
from .provider import AiError, available, complete

VERSION = "2"
PENDING_TTL = timedelta(minutes=2)


def run(
    customer,
    feature,
    system,
    context,
    validate,
    *,
    max_tokens=650,
    temperature=0.2,
    cache_ttl_seconds=3600,
):
    if not available():
        raise AiError("disabled")
    encoded = json.dumps(
        [VERSION, settings.ARVAN_AI_MODEL, feature, context],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(encoded) > 16_000:
        raise AiError("invalid_input")
    fingerprint = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    today = timezone.localdate()
    now = timezone.now()
    pending_since = now - PENDING_TTL
    try:
        cache_ttl = max(0, min(int(cache_ttl_seconds), 86_400))
    except (TypeError, ValueError):
        cache_ttl = 3600

    with transaction.atomic():
        day, _ = AiDay.objects.get_or_create(day=today)
        AiDay.objects.select_for_update().get(pk=day.pk)
        rows = AiRun.objects.filter(day=today)
        counted = rows.filter(
            Q(state="ok") | Q(state="pending", created_at__gte=pending_since)
        )
        same = rows.filter(customer=customer, feature=feature, fingerprint=fingerprint)

        cached = None
        if cache_ttl:
            cached = same.filter(
                state="ok",
                created_at__gte=now - timedelta(seconds=cache_ttl),
            ).order_by("-created_at").first()
        if cached:
            return cached.result, True

        if same.filter(state="pending", created_at__gte=pending_since).exists():
            raise AiError("busy")

        global_limit = max(0, int(getattr(settings, "ARVAN_AI_GLOBAL_DAILY_LIMIT", 200)))
        user_limit = max(0, int(getattr(settings, "ARVAN_AI_USER_DAILY_LIMIT", 10)))
        feature_limits = getattr(settings, "ARVAN_AI_FEATURE_DAILY_LIMITS", {}) or {}
        feature_limit = max(0, int(feature_limits.get(feature, 0) or 0))

        if global_limit and counted.count() >= global_limit:
            raise AiError("quota")
        customer_runs = counted.filter(customer=customer)
        if user_limit and customer_runs.count() >= user_limit:
            raise AiError("quota")
        if feature_limit and customer_runs.filter(feature=feature).count() >= feature_limit:
            raise AiError("feature_quota")
        if customer_runs.filter(created_at__gte=now - timedelta(seconds=5)).exists():
            raise AiError("busy")

        job = AiRun.objects.create(
            customer=customer,
            day=today,
            feature=feature,
            fingerprint=fingerprint,
        )

    try:
        raw, input_tokens, output_tokens = complete(
            system,
            context,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        result = validate(raw)
        if not isinstance(result, dict):
            raise AiError("invalid_output")
        AiRun.objects.filter(pk=job.pk).update(
            state="ok",
            result=result,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            error="",
        )
    except AiError as exc:
        AiRun.objects.filter(pk=job.pk).update(state="failed", error=str(exc)[:32])
        raise
    except Exception:
        AiRun.objects.filter(pk=job.pk).update(state="failed", error="internal_error")
        raise

    return result, False
