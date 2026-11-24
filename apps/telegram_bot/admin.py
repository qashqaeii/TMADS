from django.contrib import admin

from .models import (
    TelegramBotConfig,
    TelegramCallbackReceipt,
    TelegramLinkToken,
    TelegramMenuSession,
    TelegramNotificationPreference,
    TelegramOutbox,
    TelegramStaffLink,
    TelegramUpdateLog,
    TelegramUserLink,
)


@admin.register(TelegramBotConfig)
class TelegramBotConfigAdmin(admin.ModelAdmin):
    list_display = ("singleton_key", "enabled", "customer_panel_enabled", "admin_panel_enabled", "updated_at")


@admin.register(TelegramUserLink)
class TelegramUserLinkAdmin(admin.ModelAdmin):
    list_display = ("telegram_user_id", "customer", "is_active", "linked_at", "last_seen_at")
    list_filter = ("is_active",)
    search_fields = ("telegram_user_id", "customer__display_name", "telegram_username")


@admin.register(TelegramStaffLink)
class TelegramStaffLinkAdmin(admin.ModelAdmin):
    list_display = ("telegram_user_id", "user", "is_active", "linked_at")
    list_filter = ("is_active",)
    search_fields = ("telegram_user_id", "user__username")


@admin.register(TelegramUpdateLog)
class TelegramUpdateLogAdmin(admin.ModelAdmin):
    list_display = ("update_id", "update_type", "status", "telegram_user_id", "created_at")
    list_filter = ("status", "update_type")
    search_fields = ("update_id",)


@admin.register(TelegramOutbox)
class TelegramOutboxAdmin(admin.ModelAdmin):
    list_display = ("dedupe_key", "status", "telegram_user_id", "attempt_count", "created_at")
    list_filter = ("status",)


admin.site.register(TelegramLinkToken)
admin.site.register(TelegramMenuSession)
admin.site.register(TelegramCallbackReceipt)
admin.site.register(TelegramNotificationPreference)