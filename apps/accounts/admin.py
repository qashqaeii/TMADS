from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import CustomerProfile, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ("username", "email", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = DjangoUserAdmin.fieldsets + (("نقش", {"fields": ("role", "mobile", "email_verified")}),)
    add_fieldsets = DjangoUserAdmin.add_fieldsets + ((None, {"fields": ("role",)}),)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "is_suspended", "created_at")
    search_fields = ("user__username", "user__email", "display_name")
