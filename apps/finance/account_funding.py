"""Idempotent main → related account funding (orders or budget operations)."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.finance.models import AccountFundingTransfer
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.account_connections import campaign_account_snapshot


def fund_platform_managed_transfer(
    campaign,
    *,
    amount: Decimal,
    idempotency_key: str,
    order=None,
    operation=None,
) -> AccountFundingTransfer | None:
    """Move TON from the platform main account to the campaign child account once."""
    if bool(order) == bool(operation):
        raise ValueError("سند انتقال باید دقیقاً به یک سفارش یا یک عملیات بودجه متصل باشد.")
    connection = campaign.telegram_connection
    if not connection or connection.connection_type != "platform_managed":
        return None
    related = connection.related_account
    if not related or related.remote_account_id != connection.remote_account_id:
        raise ValueError("حساب مرتبط برای انتقال اعتبار معتبر نیست.")
    if not amount.is_finite() or amount <= 0:
        raise ValueError("مبلغ انتقال معتبر نیست.")

    lookup = {"order": order} if order else {"operation": operation}
    transfer, created = AccountFundingTransfer.objects.get_or_create(
        **lookup,
        defaults={
            "connection": connection,
            "direction": AccountFundingTransfer.Direction.MAIN_TO_RELATED,
            "status": AccountFundingTransfer.Status.EXECUTING,
            "amount": amount,
            "currency": "TON",
            "idempotency_key": idempotency_key,
        },
    )
    if (
        transfer.connection_id != connection.pk
        or transfer.amount != amount
        or transfer.currency != "TON"
        or transfer.idempotency_key != idempotency_key
    ):
        raise ValueError("سند انتقال اعتبار با مقصد و مبلغ مطابقت ندارد.")
    if transfer.status == AccountFundingTransfer.Status.COMPLETED:
        return transfer
    if transfer.status == AccountFundingTransfer.Status.FAILED:
        raise ValueError("انتقال اعتبار قبلی ناموفق بوده است؛ بررسی مالی لازم است.")
    if transfer.status == AccountFundingTransfer.Status.UNCERTAIN:
        raise ValueError("انتقال اعتبار نیازمند تطبیق است؛ اجرای مجدد ممنوع است.")

    try:
        result = TelegramAdsClient().transfer_to_related_account(
            account_id=related.remote_account_id,
            amount=float(amount),
            idempotency_key=idempotency_key,
        )
        transaction_id = str(result.get("transaction_id") or "").strip()
        moved = Decimal(str(result.get("amount")))
        main_account = result.get("main_account") or {}
        child_account = result.get("related_account") or {}
        valid = (
            result.get("status") == "completed"
            and transaction_id
            and result.get("currency") == "TON"
            and moved == amount
            and str(main_account.get("account_id") or "") == related.main_account_id
            and str(child_account.get("account_id") or "") == related.remote_account_id
        )
        if not valid:
            raise ValueError("پاسخ انتقال اعتبار کامل یا منطبق نیست.")
        child_snapshot = campaign_account_snapshot(campaign)
        if child_snapshot["currency"] != "TON" or child_snapshot["remaining_budget"] < amount:
            raise ValueError("موجودی حساب مرتبط پس از انتقال قابل تأیید نیست.")
        transfer.status = AccountFundingTransfer.Status.COMPLETED
        transfer.transaction_id = transaction_id
        transfer.response_payload = {
            "status": result.get("status"),
            "transaction_id": transaction_id,
            "currency": result.get("currency"),
            "amount": str(moved),
            "main_account_id": related.main_account_id,
            "related_account_id": related.remote_account_id,
        }
        transfer.confirmed_at = timezone.now()
        transfer.save(update_fields=[
            "status", "transaction_id", "response_payload", "confirmed_at", "updated_at",
        ])
        return transfer
    except Exception as exc:
        AccountFundingTransfer.objects.filter(pk=transfer.pk).update(
            status=AccountFundingTransfer.Status.UNCERTAIN,
            error_code=type(exc).__name__,
        )
        raise TelegramAdsError(
            "نتیجه انتقال اعتبار به حساب اختصاصی مشتری نیازمند تطبیق است."
        ) from exc