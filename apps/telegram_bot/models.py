from __future__ import annotations

from django.db import models

from apps.accounts.models import CustomerProfile, User
from apps.core.models import TimeStampedModel, UUIDModel


class TelegramBotConfig(UUIDModel, TimeStampedModel):
    """تنظیمات قابل‌تغییر از پنل مدیریت (توکن ربات فقط از env خوانده می‌شود)."""

    singleton_key = models.CharField(max_length=16, unique=True, default="default")
    enabled = models.BooleanField(default=False, verbose_name="فعال")
    customer_panel_enabled = models.BooleanField(default=True, verbose_name="پنل مشتری")
    admin_panel_enabled = models.BooleanField(default=True, verbose_name="پنل مدیریت")
    ai_menu_enabled = models.BooleanField(default=True, verbose_name="منوی دستیار هوشمند")
    webhook_path = models.CharField(max_length=120, default="telegram/webhook/", verbose_name="مسیر Webhook")
    max_updates_per_minute = models.PositiveSmallIntegerField(default=40, verbose_name="سقف آپدیت در دقیقه")

    class Meta:
        verbose_name = "تنظیمات ربات تلگرام"
        verbose_name_plural = "تنظیمات ربات تلگرام"

    def __str__(self) -> str:
        return "تنظیمات ربات گرام‌ادز"


class TelegramUserLink(UUIDModel, TimeStampedModel):
    """اتصال Telegram User ID به حساب مشتری در سایت."""

    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name="telegram_bot_links",
    )
    telegram_user_id = models.BigIntegerField(db_index=True)
    chat_id = models.BigIntegerField(db_index=True)
    telegram_username = models.CharField(max_length=64, blank=True)
    device_label = models.CharField(max_length=80, blank=True, verbose_name="برچسب دستگاه")
    is_active = models.BooleanField(default=True, db_index=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-linked_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["telegram_user_id"],
                condition=models.Q(is_active=True),
                name="unique_active_telegram_user_link",
            ),
        ]
        indexes = [
            models.Index(fields=["customer", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"tg:{self.telegram_user_id} → {self.customer_id}"


class TelegramLinkToken(UUIDModel, TimeStampedModel):
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="telegram_link_tokens")
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_telegram_user_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class TelegramMenuSession(TimeStampedModel):
    telegram_user_id = models.BigIntegerField(primary_key=True)
    chat_id = models.BigIntegerField()
    menu_message_id = models.BigIntegerField(null=True, blank=True)
    nav_stack = models.JSONField(default=list, blank=True)
    context = models.JSONField(default=dict, blank=True)
    panel = models.CharField(max_length=16, default="guest")  # guest | customer | admin

    class Meta:
        verbose_name = "نشست منوی ربات"


class TelegramUpdateLog(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        RECEIVED = "received", "دریافت‌شده"
        QUEUED = "queued", "در صف"
        PROCESSING = "processing", "در حال پردازش"
        DONE = "done", "انجام‌شده"
        FAILED = "failed", "ناموفق"
        DUPLICATE = "duplicate", "تکراری"

    update_id = models.BigIntegerField(unique=True, db_index=True)
    update_type = models.CharField(max_length=32, blank=True)
    telegram_user_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.RECEIVED)
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class TelegramCallbackReceipt(models.Model):
    callback_query_id = models.CharField(max_length=128, primary_key=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TelegramOutbox(UUIDModel, TimeStampedModel):
    class Status(models.TextChoices):
        QUEUED = "queued", "در صف"
        SENDING = "sending", "در حال ارسال"
        SENT = "sent", "ارسال‌شده"
        FAILED = "failed", "ناموفق"
        SKIPPED = "skipped", "رد شده"

    link = models.ForeignKey(
        TelegramUserLink,
        on_delete=models.CASCADE,
        related_name="outbox_messages",
        null=True,
        blank=True,
    )
    telegram_user_id = models.BigIntegerField(db_index=True)
    chat_id = models.BigIntegerField()
    body = models.TextField()
    reply_markup = models.JSONField(default=dict, blank=True)
    dedupe_key = models.CharField(max_length=160, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=500, blank=True)
    notification_id = models.UUIDField(null=True, blank=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class TelegramNotificationPreference(UUIDModel, TimeStampedModel):
    link = models.OneToOneField(TelegramUserLink, on_delete=models.CASCADE, related_name="notification_prefs")
    campaign_status = models.BooleanField(default=True)
    payment_events = models.BooleanField(default=True)
    budget_alerts = models.BooleanField(default=True)
    support_replies = models.BooleanField(default=True)
    security_alerts = models.BooleanField(default=True)

    class Meta:
        verbose_name = "تنظیم اعلان ربات"


class TelegramStaffLink(UUIDModel, TimeStampedModel):
    """اتصال تلگرام برای کاربران عملیاتی (پنل مدیریت ربات)."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="telegram_staff_links")
    telegram_user_id = models.BigIntegerField(db_index=True)
    chat_id = models.BigIntegerField()
    is_active = models.BooleanField(default=True, db_index=True)
    linked_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["telegram_user_id"],
                condition=models.Q(is_active=True),
                name="unique_active_telegram_staff_link",
            ),
        ]