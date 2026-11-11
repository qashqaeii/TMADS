from django.db import models

from apps.core.models import TimeStampedModel, UUIDModel


class APICapability(UUIDModel, TimeStampedModel):
    class State(models.TextChoices):
        SUPPORTED = "supported", "پشتیبانی‌شده"
        UNSUPPORTED = "unsupported", "پشتیبانی نمی‌شود"
        PERMISSION_DENIED = "permission_denied", "مجوز ندارد"
        UNVERIFIED = "unverified", "بررسی‌نشده"
        TEMPORARY = "temporary", "موقت"

    feature_key = models.CharField(max_length=120, unique=True)
    state = models.CharField(max_length=32, choices=State.choices, default=State.UNVERIFIED)
    details = models.JSONField(default=dict, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)


class APIRequestLog(UUIDModel, TimeStampedModel):
    operation = models.CharField(max_length=120, db_index=True)
    success = models.BooleanField(default=False)
    meta = models.JSONField(default=dict, blank=True)


class APIReconciliationRecord(UUIDModel, TimeStampedModel):
    notes = models.TextField(blank=True)
    central_ton_balance = models.DecimalField(max_digits=18, decimal_places=9, default=0)
    customer_reserved_irr = models.BigIntegerField(default=0)
    mismatch = models.BooleanField(default=False)
