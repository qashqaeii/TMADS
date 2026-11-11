from django.contrib import admin

from .models import ExchangeRate, Invoice, Payment, PlatformFeeRule, RefundRequest, Wallet, WalletLedgerEntry


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ("customer", "available_irr", "reserved_irr", "updated_at")
    search_fields = ("customer__user__username",)


@admin.register(WalletLedgerEntry)
class WalletLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("wallet", "entry_type", "amount_irr", "created_at")
    list_filter = ("entry_type",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("customer", "amount_irr", "gateway", "status", "created_at")
    list_filter = ("gateway", "status")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "customer", "amount_irr", "created_at")
    search_fields = ("invoice_number",)


@admin.register(RefundRequest)
class RefundRequestAdmin(admin.ModelAdmin):
    list_display = ("customer", "amount_irr", "status", "created_at")
    list_filter = ("status",)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("source", "is_active", "created_at")


@admin.register(PlatformFeeRule)
class PlatformFeeRuleAdmin(admin.ModelAdmin):
    list_display = ("percent", "is_active", "created_at")
