from django.db import models

from apps.accounts.models import CustomerProfile, User
from apps.core.models import UUIDModel, TimeStampedModel


class SupportTicket(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        OPEN = "open", "باز"
        IN_PROGRESS = "in_progress", "در حال پیگیری"
        RESOLVED = "resolved", "حل‌شده"
        CLOSED = "closed", "بسته"

    class Priority(models.TextChoices):
        LOW = "low", "کم"
        NORMAL = "normal", "معمولی"
        HIGH = "high", "بالا"

    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="tickets")
    subject = models.CharField(max_length=120)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=16, choices=Priority.choices, default=Priority.NORMAL)
    related_campaign_id = models.UUIDField(null=True, blank=True)
    related_order_id = models.UUIDField(null=True, blank=True)


class SupportMessage(UUIDModel, TimeStampedModel):
    ticket = models.ForeignKey(SupportTicket, on_delete=models.CASCADE, related_name="messages")
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    body = models.TextField()
    is_staff = models.BooleanField(default=False)
