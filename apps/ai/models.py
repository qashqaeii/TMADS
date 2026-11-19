from django.db import models
from apps.core.models import UUIDModel, TimeStampedModel
from apps.accounts.models import CustomerProfile


class AiDay(models.Model):
    day = models.DateField(primary_key=True)


class AiRun(UUIDModel, TimeStampedModel):
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="ai_runs")
    day = models.DateField(db_index=True)
    feature = models.CharField(max_length=32)
    fingerprint = models.CharField(max_length=64)
    state = models.CharField(max_length=16, default="pending")
    result = models.JSONField(default=dict)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    error = models.CharField(max_length=32, blank=True)

    class Meta:
        indexes = [models.Index(fields=["customer", "day", "feature", "fingerprint"], name="ai_run_lookup_idx")]
