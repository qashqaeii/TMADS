from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CustomerProfile

from ..models import TelegramLinkToken, TelegramNotificationPreference, TelegramStaffLink, TelegramUserLink
from ..security import digest_token, generate_link_token


LINK_TTL_MINUTES = 15


@transaction.atomic
def create_link_token(customer: CustomerProfile) -> str:
    raw = generate_link_token()
    TelegramLinkToken.objects.create(
        customer=customer,
        token_digest=digest_token(raw),
        expires_at=timezone.now() + timedelta(minutes=LINK_TTL_MINUTES),
    )
    return raw


@transaction.atomic
def consume_link_token(
    raw_token: str,
    *,
    telegram_user_id: int,
    chat_id: int,
    telegram_username: str = "",
) -> TelegramUserLink:
    digest = digest_token(raw_token.strip())
    row = (
        TelegramLinkToken.objects.select_for_update()
        .filter(token_digest=digest, consumed_at__isnull=True, expires_at__gt=timezone.now())
        .select_related("customer")
        .first()
    )
    if not row:
        raise ValueError("کد اتصال نامعتبر یا منقضی شده است.")

  # یک تلگرام فقط یک مشتری فعال
    TelegramUserLink.objects.filter(telegram_user_id=telegram_user_id, is_active=True).update(
        is_active=False,
        revoked_at=timezone.now(),
        revoked_reason="اتصال حساب جدید",
    )

    link = TelegramUserLink.objects.create(
        customer=row.customer,
        telegram_user_id=telegram_user_id,
        chat_id=chat_id,
        telegram_username=(telegram_username or "")[:64],
        device_label="تلگرام",
        is_active=True,
        last_seen_at=timezone.now(),
    )
    TelegramNotificationPreference.objects.get_or_create(link=link)
    row.consumed_at = timezone.now()
    row.consumed_telegram_user_id = telegram_user_id
    row.save(update_fields=["consumed_at", "consumed_telegram_user_id", "updated_at"])

    user = row.customer.user
    if user.is_staff_ops:
        TelegramStaffLink.objects.filter(telegram_user_id=telegram_user_id, is_active=True).exclude(user=user).update(
            is_active=False
        )
        TelegramStaffLink.objects.update_or_create(
            user=user,
            defaults={
                "telegram_user_id": telegram_user_id,
                "chat_id": chat_id,
                "is_active": True,
                "last_seen_at": timezone.now(),
            },
        )
    return link


@transaction.atomic
def revoke_link(link: TelegramUserLink, *, reason: str = "") -> None:
    if not link.is_active:
        return
    link.is_active = False
    link.revoked_at = timezone.now()
    link.revoked_reason = reason[:200]
    link.save(update_fields=["is_active", "revoked_at", "revoked_reason", "updated_at"])


def customer_active_links(customer: CustomerProfile):
    return TelegramUserLink.objects.filter(customer=customer, is_active=True).order_by("-linked_at")