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


class RelatedAccountRequest(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار بررسی"
        EXECUTING = "executing", "در حال ایجاد"
        PROVISIONED = "provisioned", "ایجاد و تأیید شده"
        REJECTED = "rejected", "رد شده"
        UNCERTAIN = "uncertain", "نیازمند تطبیق"

    customer = models.OneToOneField("accounts.CustomerProfile", on_delete=models.PROTECT, related_name="related_account_request")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    title = models.CharField(max_length=128)
    details = models.JSONField(default=dict)
    consent_at = models.DateTimeField()
    main_account_id = models.CharField(max_length=256, blank=True)
    remote_account_id = models.CharField(max_length=256, blank=True)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["main_account_id","remote_account_id"],
            condition=~models.Q(remote_account_id=""), name="unique_related_account_binding")]


class AccountAssetOperation(UUIDModel, TimeStampedModel):
    account = models.ForeignKey(RelatedAccountRequest,on_delete=models.PROTECT,related_name="asset_operations")
    action = models.CharField(max_length=16)
    state = models.CharField(max_length=16,default="executing")
    remote_id = models.CharField(max_length=256,blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["account"],
            condition=models.Q(state__in=["executing","uncertain"]),name="one_unresolved_asset_operation")]


class TargetBotCatalogEntry(UUIDModel, TimeStampedModel):
    """Curated internal bot catalog for Similar Bots recommendations (not Telegram HTML)."""

    username = models.CharField(max_length=64, unique=True, db_index=True)
    title = models.CharField(max_length=200, blank=True)
    photo_url = models.URLField(max_length=500, blank=True)
    category = models.CharField(max_length=64, blank=True, db_index=True)
    language_codes = models.JSONField(default=list, blank=True)
    topic_ids = models.JSONField(default=list, blank=True)
    tags = models.JSONField(default=list, blank=True)
    related_usernames = models.JSONField(default=list, blank=True)
    monthly_users = models.PositiveIntegerField(null=True, blank=True)
    priority = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-priority", "username"]
        verbose_name = "Target bot catalog entry"
        verbose_name_plural = "Target bot catalog entries"

    def __str__(self) -> str:
        return self.username
