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

    class Meta:
        ordering = ["-created_at"]
