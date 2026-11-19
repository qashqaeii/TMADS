from decimal import Decimal

from django.db import models

from apps.accounts.models import CustomerProfile
from apps.core.models import TenantOwnedModel, TimeStampedModel, UUIDModel


class Wallet(TenantOwnedModel):
    customer = models.OneToOneField(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="wallet",
    )
    available_irr = models.BigIntegerField(default=0)
    reserved_irr = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(available_irr__gte=0),
                name="wallet_available_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(reserved_irr__gte=0),
                name="wallet_reserved_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"Wallet {self.customer_id}"


class WalletLedgerEntry(UUIDModel, TimeStampedModel):
    class EntryType(models.TextChoices):
        DEPOSIT = "deposit", "واریز"
        RESERVATION = "reservation", "رزرو"
        RESERVATION_RELEASE = "reservation_release", "آزادسازی رزرو"
        CREDIT_ALLOCATION = "credit_allocation", "تخصیص اعتبار تبلیغاتی"
        SPEND = "spend", "هزینه تبلیغ"
        SERVICE_FEE = "service_fee", "کارمزد سرویس"
        REFUND = "refund", "بازپرداخت"
        ADJUSTMENT = "adjustment", "تعدیل دستی"

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="ledger_entries")
    entry_type = models.CharField(max_length=32, choices=EntryType.choices)
    amount_irr = models.BigIntegerField()
    balance_after_available = models.BigIntegerField()
    balance_after_reserved = models.BigIntegerField()
    idempotency_key = models.CharField(max_length=128, unique=True)
    description = models.CharField(max_length=255, blank=True)
    related_order_id = models.UUIDField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class ExchangeRate(UUIDModel, TimeStampedModel):
    ton_per_irr = models.DecimalField(max_digits=24, decimal_places=12)
    source = models.CharField(max_length=120, default="manual")
    is_active = models.BooleanField(default=True)
    details = models.JSONField(default=dict, blank=True)


class PlatformFeeRule(UUIDModel, TimeStampedModel):
    percent = models.PositiveSmallIntegerField(default=5)
    is_active = models.BooleanField(default=True)


class AdvertisingOrder(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        AWAITING_PAYMENT = "awaiting_payment", "در انتظار پرداخت"
        PAYMENT_PENDING = "payment_pending", "پرداخت در جریان"
        PAID = "paid", "پرداخت‌شده"
        READY_FOR_SUBMISSION = "ready", "آماده ارسال"
        SUBMITTING = "submitting", "در حال ارسال"
        COMPLETED = "completed", "تکمیل"
        CANCELLED = "cancelled", "لغو"
        FAILED = "failed", "ناموفق"

    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="orders")
    campaign_id = models.UUIDField(db_index=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    quote_expires_at = models.DateTimeField(null=True, blank=True)

    advertising_budget_irr = models.BigIntegerField(default=0)
    service_fee_irr = models.BigIntegerField(default=0)
    total_irr = models.BigIntegerField(default=0)
    ton_allocation = models.DecimalField(max_digits=18, decimal_places=9, default=Decimal("0"))
    exchange_rate_id = models.UUIDField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class PriceQuote(UUIDModel, TimeStampedModel):
    order = models.OneToOneField(AdvertisingOrder, on_delete=models.CASCADE, related_name="quote")
    payload = models.JSONField(default=dict)
    expires_at = models.DateTimeField()
    locked_total_irr = models.BigIntegerField()


class Payment(TenantOwnedModel):
    class Status(models.TextChoices):
        CREATED = "created", "ایجاد شده"
        REDIRECTED = "redirected", "هدایت به درگاه"
        VERIFIED = "verified", "تأیید شده"
        FAILED = "failed", "ناموفق"

    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="payments")
    order = models.ForeignKey(
        AdvertisingOrder,
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True,
    )
    amount_irr = models.BigIntegerField()
    gateway = models.CharField(max_length=32, default="fake")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CREATED)
    provider_reference = models.CharField(max_length=128, blank=True)
    provider_amount_irr = models.BigIntegerField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=128, unique=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["gateway", "provider_reference"],
            condition=~models.Q(provider_reference=""), name="unique_payment_gateway_reference")]


class PaymentVerification(UUIDModel, TimeStampedModel):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="verifications")
    success = models.BooleanField()
    raw_payload = models.JSONField(default=dict)


class Invoice(TenantOwnedModel):
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="invoices")
    payment = models.ForeignKey(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    order = models.ForeignKey(AdvertisingOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    invoice_number = models.CharField(max_length=32, unique=True)
    amount_irr = models.BigIntegerField()
    description = models.CharField(max_length=255, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]


class RefundRequest(TenantOwnedModel):
    class Status(models.TextChoices):
        OPEN = "open", "باز"
        REVIEW = "review", "بررسی"
        APPROVED = "approved", "تأیید"
        REJECTED = "rejected", "رد"
        PAID = "paid", "پرداخت‌شده"

    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="refund_requests")
    order = models.ForeignKey(AdvertisingOrder, on_delete=models.CASCADE, related_name="refund_requests")
    amount_irr = models.BigIntegerField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    reason = models.TextField(blank=True)
