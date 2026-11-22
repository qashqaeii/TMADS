from django.contrib import admin

from apps.telegram_ads.models import TargetBotCatalogEntry


@admin.register(TargetBotCatalogEntry)
class TargetBotCatalogEntryAdmin(admin.ModelAdmin):
    list_display = ("username", "title", "category", "monthly_users", "priority", "is_active", "updated_at")
    list_filter = ("is_active", "category")
    search_fields = ("username", "title", "tags")
    ordering = ("-priority", "username")
