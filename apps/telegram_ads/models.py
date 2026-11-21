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
    connection = models.ForeignKey("telegram_ads.TelegramAdsConnection", on_delete=models.PROTECT, related_name="asset_operations")
    action = models.CharField(max_length=16)
    state = models.CharField(max_length=16,default="executing")
    remote_id = models.CharField(max_length=256,blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["connection"],
            condition=models.Q(state__in=["executing","uncertain"]),name="one_unresolved_asset_operation")]


class TelegramAdsConnection(UUIDModel, TimeStampedModel):
    """A customer's isolated Telegram Ads account connection.

    Customer-owned connections keep an encrypted API token. Platform-managed
    connections reference exactly one provisioned related account and never
    store the platform token on the customer row.
    """

    class Type(models.TextChoices):
        CUSTOMER_OWNED = "customer_owned", "حساب اختصاصی مشتری"
        PLATFORM_MANAGED = "platform_managed", "حساب مدیریت‌شده پلتفرم"

    class Status(models.TextChoices):
        CONNECTED = "connected", "متصل"
        ERROR = "error", "نیازمند بررسی"
        DISCONNECTED = "disconnected", "قطع‌شده"

    customer = models.ForeignKey(
        "accounts.CustomerProfile",
        on_delete=models.CASCADE,
        related_name="telegram_ads_connections",
    )
    connection_type = models.CharField(max_length=24, choices=Type.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CONNECTED)
    remote_account_id = models.CharField(max_length=256)
    account_title = models.CharField(max_length=200, blank=True)
    currency = models.CharField(max_length=8, blank=True)
    remaining_budget = models.DecimalField(max_digits=24, decimal_places=9, default=0)
    encrypted_access_token = models.TextField(blank=True)
    token_fingerprint = models.CharField(max_length=64, blank=True)
    related_account = models.OneToOneField(
        "telegram_ads.RelatedAccountRequest",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="telegram_connection",
    )
    is_default = models.BooleanField(default=False, db_index=True)
    capabilities = models.JSONField(default=dict, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "connection_type"],
                name="unique_customer_telegram_connection_type",
            ),
            models.UniqueConstraint(
                fields=["remote_account_id"],
                condition=~models.Q(remote_account_id=""),
                name="unique_telegram_remote_account_binding",
            ),
            models.UniqueConstraint(
                fields=["token_fingerprint"],
                condition=~models.Q(token_fingerprint=""),
                name="unique_telegram_token_fingerprint",
            ),
            models.UniqueConstraint(
                fields=["customer"],
                condition=models.Q(is_default=True),
                name="unique_default_telegram_connection_per_customer",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        connection_type="customer_owned",
                        encrypted_access_token__gt="",
                        token_fingerprint__gt="",
                        related_account__isnull=True,
                    )
                    | models.Q(
                        connection_type="platform_managed",
                        encrypted_access_token="",
                        token_fingerprint="",
                        related_account__isnull=False,
                    )
                ),
                name="telegram_connection_credentials_match_type",
            ),
        ]

    @property
    def is_customer_owned(self) -> bool:
        return self.connection_type == self.Type.CUSTOMER_OWNED

    @property
    def has_available_balance(self) -> bool:
        return self.status == self.Status.CONNECTED and self.remaining_budget > 0

    def __str__(self) -> str:
        return f"{self.customer_id}:{self.connection_type}:{self.remote_account_id}"
