from django.db import models

from apps.accounts.models import CustomerProfile
from apps.core.models import UUIDModel, TimeStampedModel


class Notification(UUIDModel, TimeStampedModel):
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    level = models.CharField(max_length=16, default="info")
    is_read = models.BooleanField(default=False)
    related_campaign_id = models.UUIDField(null=True, blank=True)
    event_key = models.CharField(max_length=160, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(
            fields=["customer", "event_key"],
            condition=~models.Q(event_key=""),
            name="one_notification_per_customer_event",
        )]


class SmsContact(UUIDModel, TimeStampedModel):
    customer = models.OneToOneField(CustomerProfile, on_delete=models.CASCADE, related_name="sms_contact")
    phone = models.CharField(max_length=11, unique=True)
    enabled = models.BooleanField(default=True)


class SmsOutbox(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "در صف"
        SENDING = "sending", "در حال ارسال"
        ACCEPTED = "accepted", "پذیرفته‌شده توسط پنل"
        FAILED = "failed", "ناموفق"
        UNKNOWN = "unknown", "نتیجه نامشخص"
        SKIPPED = "skipped", "ارسال نشد"
        SIMULATED = "simulated", "آزمایشی"

    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="sms_messages")
    event_key = models.CharField(max_length=160)
    purpose = models.CharField(max_length=32)
    phone = models.CharField(max_length=11)
    attributes = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    provider_id = models.CharField(max_length=128, blank=True)
    error_code = models.CharField(max_length=48, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["customer", "event_key"], name="one_sms_per_customer_event")]


class SmsOtp(UUIDModel, TimeStampedModel):
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="sms_otps")
    phone = models.CharField(max_length=11, db_index=True)
    digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed = models.BooleanField(default=False)
    accepted = models.BooleanField(default=False)


class SmsPhoneThrottle(models.Model):
    phone = models.CharField(max_length=11, primary_key=True)
