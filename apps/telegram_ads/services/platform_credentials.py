"""Secure operator-managed central Telegram Ads API token."""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.models import AuditLog
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsNotConfigured
from apps.telegram_ads.models import RelatedAccountRequest, TelegramAdsConnection, TelegramAdsPlatformCredential
from apps.telegram_ads.services.account_connections import (
    _account_snapshot, decrypt_access_token, encrypt_access_token,
)


def active_platform_token() -> str:
    """Prefer DB; never silently fall back to env for a disabled or corrupt DB record."""
    row = TelegramAdsPlatformCredential.objects.filter(slot="primary").first()
    if row is not None:
        if not row.is_active or not row.encrypted_access_token:
            raise TelegramAdsNotConfigured("اتصال حساب مرکزی پلتفرم غیرفعال است.")
        try:
            return decrypt_access_token(row)
        except ValueError:
            raise TelegramAdsNotConfigured("رمزگشایی توکن مرکزی ممکن نیست.") from None
    return str(getattr(settings, "TELEGRAM_ADS_API_TOKEN", "") or "")


def platform_token_is_configured() -> bool:
    row = TelegramAdsPlatformCredential.objects.filter(slot="primary").first()
    if row is not None:
        return bool(row.is_active and row.encrypted_access_token and
                    len(str(getattr(settings, "TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY", "") or "")) >= 32)
    return bool(getattr(settings, "TELEGRAM_ADS_API_TOKEN", ""))


def configure_platform_token(actor, raw_token: str) -> TelegramAdsPlatformCredential:
    """Read-only API verification before changing the one central credential."""
    if not getattr(actor, "is_authenticated", False) or not actor.is_platform_manager:
        raise PermissionDenied
    token = str(raw_token or "").strip()
    encrypted = encrypt_access_token(token)
    snapshot = _account_snapshot(TelegramAdsClient(token=token))
    if snapshot["currency"] != "TON":
        raise ValueError("حساب مرکزی برای تبلیغات مدیریت‌شده باید TON باشد.")
    account_id = snapshot["account_id"]
    if TelegramAdsConnection.objects.filter(remote_account_id=account_id).exists():
        raise ValueError("این حساب قبلاً به یک مشتری اختصاص داده شده است.")
    if RelatedAccountRequest.objects.exclude(main_account_id="").exclude(main_account_id=account_id).exists():
        raise ValueError("شناسه حساب مرکزی با حساب‌های مرتبط موجود مطابقت ندارد.")
    existing = TelegramAdsPlatformCredential.objects.filter(slot="primary").first()
    if existing and existing.remote_account_id and existing.remote_account_id != account_id:
        raise ValueError("تعویض به حساب مرکزی دیگری مجاز نیست؛ توکن باید برای همان حساب باشد.")

    from apps.campaigns.models import Campaign, TelegramAdvertisement
    has_legacy = (
        TelegramAdvertisement.objects.filter(campaign__telegram_connection__isnull=True)
        .exclude(remote_ad_id="").exists()
        or Campaign.objects.filter(
            telegram_connection__isnull=True,
            status__in=[
                Campaign.Status.READY_FOR_SUBMISSION, Campaign.Status.SUBMITTING,
                Campaign.Status.AWAITING_TELEGRAM, Campaign.Status.RECONCILIATION,
            ],
        ).exists()
    )
    if has_legacy and not existing:
        bootstrap = str(getattr(settings, "TELEGRAM_ADS_API_TOKEN", "") or "").strip()
        if not bootstrap:
            raise ValueError("برای کمپین‌های قدیمی ابتدا باید هویت حساب مرکزی قبلی تأیید شود.")
        old_account = TelegramAdsClient(token=bootstrap).get_account()
        if str(old_account.get("account_id") or "") != account_id:
            raise ValueError("حساب جدید با حساب تبلیغات قدیمی مطابقت ندارد.")

    with transaction.atomic():
        row, created = TelegramAdsPlatformCredential.objects.select_for_update().get_or_create(
            slot="primary",
            defaults={"encrypted_access_token": encrypted},
        )
        if row.remote_account_id and row.remote_account_id != account_id:
            raise ValueError("حساب مرکزی هم‌زمان تغییر کرده است؛ دوباره بررسی کنید.")
        row.encrypted_access_token = encrypted
        row.token_fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
        row.remote_account_id = account_id
        row.account_title = snapshot["title"]
        row.currency = snapshot["currency"]
        row.remaining_budget = snapshot["remaining_budget"]
        row.is_active = True
        row.last_checked_at = timezone.now()
        row.save()
        AuditLog.objects.create(
            actor=actor,
            action="telegram_platform_token.created" if created else "telegram_platform_token.rotated",
            entity_type="telegram_platform_credential", entity_id=row.pk,
            new_state={"remote_account_id": account_id, "currency": snapshot["currency"]},
        )
    return row
