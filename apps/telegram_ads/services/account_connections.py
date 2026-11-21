"""Secure customer account connections and a single account-scoped client resolver."""

from __future__ import annotations

import base64
import hashlib
from decimal import Decimal, InvalidOperation

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import CustomerProfile
from apps.core.models import AuditLog
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.models import RelatedAccountRequest, TelegramAdsConnection

SUPPORTED_CURRENCIES = frozenset({"TON", "EUR", "XTR"})


def _fernet() -> Fernet:
    secret = str(getattr(settings, "TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY", "") or "")
    if len(secret) < 32:
        raise ValueError("کلید رمزنگاری توکن تلگرام در تنظیمات سرور تعریف نشده است.")
    # Derive a Fernet-compatible key from a dedicated high-entropy deployment secret.
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_access_token(token: str) -> str:
    value = str(token or "").strip()
    if not value or len(value) > 4096:
        raise ValueError("توکن API معتبر نیست.")
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_access_token(connection: TelegramAdsConnection) -> str:
    if not connection.encrypted_access_token:
        raise ValueError("توکن اتصال این حساب در دسترس نیست.")
    try:
        return _fernet().decrypt(connection.encrypted_access_token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError):
        raise ValueError("رمزگشایی توکن ممکن نشد؛ کلید رمزنگاری سرور را بررسی کنید.") from None


def _account_snapshot(client: TelegramAdsClient, *, expected_id: str | None = None) -> dict:
    account = client.get_account()
    account_id = str(account.get("account_id") or "").strip()
    currency = str(account.get("currency") or "").upper()
    try:
        balance = Decimal(str(account.get("remaining_budget")))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("موجودی حساب تلگرام قابل تأیید نیست.") from None
    if not account_id or len(account_id) > 256:
        raise ValueError("شناسه حساب تبلیغاتی از تلگرام معتبر نیست.")
    if expected_id and account_id != str(expected_id):
        raise ValueError("توکن یا حساب مرتبط به حساب ثبت‌شده تعلق ندارد.")
    if currency not in SUPPORTED_CURRENCIES:
        raise ValueError("ارز حساب تلگرام توسط نسخه فعلی API پشتیبانی نمی‌شود.")
    if not balance.is_finite() or balance < 0:
        raise ValueError("موجودی حساب تلگرام معتبر نیست.")

    info = client.get_account_info()
    info_id = str(info.get("account_id") or "").strip()
    if info_id and info_id != account_id:
        raise ValueError("اطلاعات حساب از دو درخواست API با هم مطابقت ندارند.")
    return {
        "account_id": account_id,
        "currency": currency,
        "remaining_budget": balance,
        "title": str(info.get("title") or account.get("title") or "")[:200],
        "account_info": info,
    }


def connection_client(connection: TelegramAdsConnection, *, allow_error: bool = False) -> TelegramAdsClient:
    if connection.status == TelegramAdsConnection.Status.DISCONNECTED:
        raise ValueError("اتصال حساب تلگرام قطع شده است؛ دوباره متصل شوید.")
    if connection.status == TelegramAdsConnection.Status.ERROR and not allow_error:
        raise ValueError("اتصال حساب نیازمند بررسی است؛ ابتدا وضعیت اتصال را به‌روزرسانی کنید.")
    if connection.connection_type == TelegramAdsConnection.Type.CUSTOMER_OWNED:
        return TelegramAdsClient(token=decrypt_access_token(connection))
    related = connection.related_account
    if (
        not related
        or related.customer_id != connection.customer_id
        or related.status != RelatedAccountRequest.Status.PROVISIONED
        or not related.remote_account_id
        or related.remote_account_id != connection.remote_account_id
    ):
        raise ValueError("حساب مدیریت‌شده هنوز ایجاد یا تأیید نشده است.")
    return TelegramAdsClient(account_id=connection.remote_account_id)


def _apply_snapshot(connection: TelegramAdsConnection, snapshot: dict) -> None:
    connection.remote_account_id = snapshot["account_id"]
    connection.account_title = snapshot["title"]
    connection.currency = snapshot["currency"]
    connection.remaining_budget = snapshot["remaining_budget"]
    connection.status = TelegramAdsConnection.Status.CONNECTED
    connection.last_checked_at = timezone.now()
    connection.last_error = ""
    capabilities = dict(connection.capabilities or {})
    capabilities.update({
        "account.read": "supported",
        "account.info": "supported",
        # Telegram exposes no safe, non-mutating createAd permission probe.
        "ads.create": capabilities.get("ads.create") or "unverified",
        "ads.create_probe": "not_performed_to_avoid_creating_a_real_ad",
    })
    connection.capabilities = capabilities


def refresh_connection(connection: TelegramAdsConnection) -> TelegramAdsConnection:
    client = connection_client(connection, allow_error=True)
    try:
        snapshot = _account_snapshot(client, expected_id=connection.remote_account_id)
    except Exception as exc:
        connection.status = TelegramAdsConnection.Status.ERROR
        connection.last_checked_at = timezone.now()
        connection.last_error = str(exc)[:500]
        connection.save(update_fields=["status", "last_checked_at", "last_error", "updated_at"])
        raise
    _apply_snapshot(connection, snapshot)
    connection.save(update_fields=[
        "remote_account_id", "account_title", "currency", "remaining_budget",
        "status", "last_checked_at", "last_error", "capabilities", "updated_at",
    ])
    return connection


@transaction.atomic
def connect_customer_owned_account(actor, raw_token: str) -> TelegramAdsConnection:
    profile = getattr(actor, "customer_profile", None)
    if not profile or profile.is_suspended:
        raise PermissionDenied
    if not getattr(settings, "TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED", False):
        raise ValueError("اتصال حساب اختصاصی مشتری هنوز در تنظیمات پلتفرم فعال نشده است.")
    token = str(raw_token or "").strip()
    encrypted = encrypt_access_token(token)
    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()

    # Verify the supplied token against Telegram before persisting any credential.
    client = TelegramAdsClient(token=token)
    snapshot = _account_snapshot(client)
    if TelegramAdsConnection.objects.filter(token_fingerprint=fingerprint).exclude(customer=profile).exists():
        raise ValueError("این توکن قبلاً به حساب مشتری دیگری متصل شده است.")
    if TelegramAdsConnection.objects.filter(remote_account_id=snapshot["account_id"]).exclude(customer=profile).exists():
        raise ValueError("این حساب تلگرام قبلاً به مشتری دیگری متصل شده است.")

    existing = TelegramAdsConnection.objects.select_for_update().filter(
        customer=profile, connection_type=TelegramAdsConnection.Type.CUSTOMER_OWNED,
    ).first()
    if existing and existing.remote_account_id != snapshot["account_id"]:
        from apps.campaigns.models import Campaign
        if Campaign.objects.filter(telegram_connection=existing).exists():
            raise ValueError("این اتصال به کمپین‌های قبلی متصل است؛ برای جلوگیری از تغییر مالکیت، حساب دیگری را جایگزین نکنید.")

    if existing:
        connection = existing
        if connection.token_fingerprint != fingerprint:
            connection.capabilities = {**(connection.capabilities or {}), "ads.create": "unverified"}
        connection.encrypted_access_token = encrypted
        connection.token_fingerprint = fingerprint
        connection.remote_account_id = snapshot["account_id"]
        connection.is_default = connection.is_default or not TelegramAdsConnection.objects.filter(
            customer=profile, is_default=True,
        ).exclude(pk=connection.pk).exists()
    else:
        connection = TelegramAdsConnection(
            customer=profile,
            connection_type=TelegramAdsConnection.Type.CUSTOMER_OWNED,
            encrypted_access_token=encrypted,
            token_fingerprint=fingerprint,
            is_default=not TelegramAdsConnection.objects.filter(customer=profile, is_default=True).exists(),
        )
    _apply_snapshot(connection, snapshot)
    try:
        connection.save()
    except IntegrityError:
        raise ValueError("این حساب یا توکن قبلاً در پلتفرم ثبت شده است.") from None
    AuditLog.objects.create(
        actor=actor,
        action="telegram_connection.customer_owned_connected",
        entity_type="telegram_ads_connection",
        entity_id=connection.pk,
        new_state={
            "connection_type": connection.connection_type,
            "remote_account_id": connection.remote_account_id,
            "currency": connection.currency,
        },
    )
    return connection


@transaction.atomic
def ensure_platform_managed_connection(row: RelatedAccountRequest, *, actor=None) -> TelegramAdsConnection:
    row = RelatedAccountRequest.objects.select_for_update().select_related("customer").get(pk=row.pk)
    if row.status != RelatedAccountRequest.Status.PROVISIONED or not row.remote_account_id:
        raise ValueError("حساب مرتبط هنوز از سوی تلگرام تأیید نشده است.")
    main_client = TelegramAdsClient()
    main = main_client.get_account()
    if (
        not row.main_account_id
        or str(main.get("account_id") or "") != row.main_account_id
        or row.main_account_id == row.remote_account_id
    ):
        raise ValueError("مالکیت حساب مرکزی و حساب مرتبط قابل تأیید نیست.")
    child_client = TelegramAdsClient(account_id=row.remote_account_id)
    snapshot = _account_snapshot(child_client, expected_id=row.remote_account_id)
    if snapshot["currency"] != "TON":
        raise ValueError("حساب مدیریت‌شده باید با ارز TON ایجاد شود؛ مسیر مالی فعلی پلتفرم فقط TON را پشتیبانی می‌کند.")

    connection = TelegramAdsConnection.objects.select_for_update().filter(
        customer=row.customer, connection_type=TelegramAdsConnection.Type.PLATFORM_MANAGED,
    ).first()
    if connection and connection.related_account_id != row.pk:
        raise ValueError("حساب مدیریت‌شده دیگری به این مشتری متصل است.")
    if not connection:
        connection = TelegramAdsConnection(
            customer=row.customer,
            connection_type=TelegramAdsConnection.Type.PLATFORM_MANAGED,
            related_account=row,
            is_default=not TelegramAdsConnection.objects.filter(customer=row.customer, is_default=True).exists(),
        )
    _apply_snapshot(connection, snapshot)
    connection.related_account = row
    connection.encrypted_access_token = ""
    connection.token_fingerprint = ""
    try:
        connection.save()
    except IntegrityError:
        raise ValueError("این حساب مرتبط قبلاً به مشتری دیگری متصل شده است.") from None
    if actor:
        AuditLog.objects.create(
            actor=actor,
            action="telegram_connection.platform_managed_connected",
            entity_type="telegram_ads_connection",
            entity_id=connection.pk,
            new_state={
                "connection_type": connection.connection_type,
                "remote_account_id": connection.remote_account_id,
                "currency": connection.currency,
            },
        )
    return connection


def default_connection(customer: CustomerProfile) -> TelegramAdsConnection | None:
    return TelegramAdsConnection.objects.filter(
        customer=customer,
        is_default=True,
        status=TelegramAdsConnection.Status.CONNECTED,
    ).first() or TelegramAdsConnection.objects.filter(
        customer=customer,
        status=TelegramAdsConnection.Status.CONNECTED,
    ).first()


@transaction.atomic
def set_default_connection(actor, connection_id) -> TelegramAdsConnection:
    profile = getattr(actor, "customer_profile", None)
    if not profile or profile.is_suspended:
        raise PermissionDenied
    connection = TelegramAdsConnection.objects.select_for_update().get(
        pk=connection_id, customer=profile, status=TelegramAdsConnection.Status.CONNECTED,
    )
    TelegramAdsConnection.objects.filter(customer=profile, is_default=True).exclude(pk=connection.pk).update(
        is_default=False,
    )
    if not connection.is_default:
        connection.is_default = True
        connection.save(update_fields=["is_default", "updated_at"])
    AuditLog.objects.create(
        actor=actor,
        action="telegram_connection.default_changed",
        entity_type="telegram_ads_connection",
        entity_id=connection.pk,
        new_state={"remote_account_id": connection.remote_account_id},
    )
    return connection


def campaign_client(campaign: "Campaign") -> TelegramAdsClient:
    """Resolve one immutable account identity for every campaign API operation.

    A null FK is reserved for legacy campaigns created before account binding;
    those continue to use the original platform main account.
    """
    connection = getattr(campaign, "telegram_connection", None)
    if connection is None:
        return TelegramAdsClient()
    if connection.customer_id != campaign.customer_id:
        raise PermissionDenied
    return connection_client(connection)


def campaign_account_snapshot(campaign: "Campaign") -> dict:
    connection = getattr(campaign, "telegram_connection", None)
    client = campaign_client(campaign)
    snapshot = _account_snapshot(
        client,
        expected_id=connection.remote_account_id if connection else None,
    )
    if connection:
        _apply_snapshot(connection, snapshot)
        connection.save(update_fields=[
            "account_title", "currency", "remaining_budget", "status",
            "last_checked_at", "last_error", "capabilities", "updated_at",
        ])
    return snapshot
