from django.db import models

from apps.accounts.models import CustomerProfile
from apps.core.models import TenantOwnedModel, UUIDModel


class AdvertisingProject(TenantOwnedModel):
    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=200)

    class Meta:
        ordering = ["-created_at"]


class Campaign(TenantOwnedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        AWAITING_PAYMENT = "awaiting_payment", "در انتظار پرداخت"
        PAYMENT_PENDING = "payment_pending", "پرداخت در جریان"
        PAID = "paid", "پرداخت‌شده"
        PENDING_REVIEW = "pending_review", "در انتظار بررسی"
        READY_FOR_SUBMISSION = "ready_for_submission", "آماده ارسال"
        SUBMITTING = "submitting", "در حال ارسال"
        AWAITING_TELEGRAM = "awaiting_telegram", "در انتظار تأیید تلگرام"
        ACTIVE = "active", "فعال"
        PAUSED = "paused", "متوقف"
        REJECTED = "rejected", "رد شده"
        COMPLETED = "completed", "پایان‌یافته"
        CANCELLED = "cancelled", "لغو"
        FAILED = "failed", "ناموفق"
        RECONCILIATION = "reconciliation", "نیازمند تطبیق"

    class Objective(models.TextChoices):
        BOT = "bot", "ربات تلگرام"
        CHANNEL = "channel", "کانال تلگرام"
        MINI_APP = "mini_app", "مینی‌اپ"
        WEBSITE = "website", "وب‌سایت"

    class Placement(models.TextChoices):
        SEARCH = "search_result", "نتایج جستجو"
        BOT_BANNER = "bot_banner", "بنر ربات"
        CHANNEL_POST = "channel_post", "پست کانال"
        VIDEO_BANNER = "video_banner", "بنر ویدیو"
        # Legacy wizard values (mapped on save)
        CHANNELS = "channels", "کانال‌ها (قدیمی)"
        VIDEO = "video", "ویدیو (قدیمی)"

    class TargetType(models.TextChoices):
        SEARCH = "search", "جستجو"
        BOTS = "bots", "ربات‌ها"
        USERS = "users", "کاربران"
        CHANNELS = "channels", "کانال‌ها"

    customer = models.ForeignKey(CustomerProfile, on_delete=models.CASCADE, related_name="campaigns")
    project = models.ForeignKey(
        AdvertisingProject,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )
    name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    objective = models.CharField(max_length=32, choices=Objective.choices, blank=True)
    destination = models.CharField(max_length=500, blank=True)
    placement = models.CharField(max_length=32, choices=Placement.choices, blank=True)
    target_type = models.CharField(max_length=16, choices=TargetType.choices, blank=True)
    wizard_version = models.PositiveSmallIntegerField(default=2)
    wizard_step = models.PositiveSmallIntegerField(default=1)
    wizard_data = models.JSONField(default=dict, blank=True)
    ad_settings = models.JSONField(default=dict, blank=True)
    draft_revision = models.PositiveIntegerField(default=0)
    draft_saved_at = models.DateTimeField(null=True, blank=True)

    budget_irr = models.BigIntegerField(default=0)
    daily_cap_irr = models.BigIntegerField(default=0)
    cpm_bid = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    schedule_start = models.DateTimeField(null=True, blank=True)
    schedule_end = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "status"]),
        ]


class AdCreative(TenantOwnedModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="creatives")
    title = models.CharField(max_length=200, blank=True)
    ad_text = models.TextField(blank=True)
    cta_label = models.CharField(max_length=64, blank=True)
    media = models.FileField(upload_to="ad_media/", blank=True)

    class Meta:
        ordering = ["-created_at"]


class CampaignTargeting(TenantOwnedModel):
    campaign = models.OneToOneField(Campaign, on_delete=models.CASCADE, related_name="targeting")
    config = models.JSONField(default=dict, blank=True)


class TelegramAdvertisement(TenantOwnedModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="remote_ads")
    remote_ad_id = models.CharField(max_length=64, blank=True, db_index=True)
    remote_status = models.CharField(max_length=64, blank=True)
    remote_status_raw = models.JSONField(default=dict, blank=True)
    placement = models.CharField(max_length=64, blank=True)
    promotion_url = models.URLField(max_length=500, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["remote_ad_id"],
                condition=~models.Q(remote_ad_id=""),
                name="unique_remote_ad_id_when_set",
            ),
        ]


class CampaignStatisticsSnapshot(TenantOwnedModel):
    advertisement = models.ForeignKey(
        TelegramAdvertisement,
        on_delete=models.CASCADE,
        related_name="statistics",
    )
    snapshot_date = models.DateField(db_index=True)
    impressions = models.BigIntegerField(default=0)
    clicks = models.BigIntegerField(default=0)
    actions = models.BigIntegerField(default=0)
    spent_ton = models.DecimalField(max_digits=18, decimal_places=9, default=0)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["advertisement", "snapshot_date"],
                name="unique_ad_daily_snapshot",
            ),
        ]
        ordering = ["-snapshot_date"]


class CampaignStatusHistory(UUIDModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(max_length=32, blank=True)
    to_status = models.CharField(max_length=32)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RemoteAdOperation(TenantOwnedModel):
    class Action(models.TextChoices):
        PAUSE = "pause", "توقف تبلیغ"
        RESUME = "resume", "ادامه تبلیغ"
        REVIEW = "review", "ارسال مجدد برای بررسی"
        EDIT_CPM = "edit_cpm", "تغییر CPM"
        EDIT_DAILY_LIMIT = "edit_daily_limit", "تغییر سقف روزانه"
        EDIT_TITLE = "edit_title", "تغییر عنوان داخلی"
        INCREASE_BUDGET = "increase_budget", "افزایش اعتبار تبلیغ"
        DECREASE_BUDGET = "decrease_budget", "کاهش اعتبار تبلیغ"

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار اپراتور"
        EXECUTING = "executing", "در حال اجرا"
        COMPLETED = "completed", "انجام‌شده"
        REJECTED = "rejected", "رد شده"
        UNCERTAIN = "uncertain", "نیازمند تطبیق"

    advertisement = models.ForeignKey(TelegramAdvertisement, on_delete=models.PROTECT, related_name="operations")
    action = models.CharField(max_length=24, choices=Action.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    request_payload = models.JSONField(default=dict)
    result_payload = models.JSONField(default=dict)
    note = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["advertisement"],
                condition=models.Q(status__in=["pending", "executing", "uncertain"]),
                name="unique_open_remote_ad_operation"),
        ]
