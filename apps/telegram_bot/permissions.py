from __future__ import annotations

from apps.accounts.models import User

from .models import TelegramStaffLink, TelegramUserLink


def active_customer_link(telegram_user_id: int) -> TelegramUserLink | None:
    return (
        TelegramUserLink.objects.filter(telegram_user_id=telegram_user_id, is_active=True)
        .select_related("customer", "customer__user")
        .first()
    )


def active_staff_link(telegram_user_id: int) -> TelegramStaffLink | None:
    return (
        TelegramStaffLink.objects.filter(telegram_user_id=telegram_user_id, is_active=True)
        .select_related("user")
        .first()
    )


def user_may_use_admin_panel(user: User) -> bool:
    return bool(user and user.is_authenticated and user.is_staff_ops)


def user_may_use_sensitive_admin(user: User) -> bool:
    return bool(user and user.is_authenticated and user.is_platform_manager)