"""Read-only reconciliation for uncertain platform account funding transfers."""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.core.models import AuditLog
from apps.finance.models import AccountFundingTransfer
from apps.telegram_ads.client import TelegramAdsClient


def _manager(actor) -> None:
    if not actor.is_authenticated or not actor.is_platform_manager:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied


def _parse_completed(status_payload: dict, *, transfer: AccountFundingTransfer) -> dict:
    if status_payload.get("status") != "completed":
        raise ValueError("تراکنش هنوز کامل نشده یا ناموفق است.")
    transaction_id = str(status_payload.get("transaction_id") or transfer.transaction_id or "").strip()
    if not transaction_id:
        raise ValueError("شناسه تراکنش در پاسخ تلگرام موجود نیست.")
    try:
        amount = Decimal(str(status_payload.get("amount")))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("مبلغ تراکنش قابل تأیید نیست.") from None
    if amount != transfer.amount or status_payload.get("currency") != transfer.currency:
        raise ValueError("مبلغ یا ارز تراکنش با سند انتقال مطابقت ندارد.")
    return {
        "status": "completed",
        "transaction_id": transaction_id,
        "amount": str(amount),
        "currency": transfer.currency,
        "reconciled_at": timezone.now().isoformat(),
    }


@transaction.atomic
def reconcile_uncertain_funding_transfer(transfer_id, *, actor) -> AccountFundingTransfer:
    _manager(actor)
    transfer = AccountFundingTransfer.objects.select_for_update().select_related("connection").get(
        pk=transfer_id,
    )
    if transfer.status != AccountFundingTransfer.Status.UNCERTAIN:
        raise ValueError("فقط انتقال‌های نیازمند تطبیق قابل بررسی هستند.")
    if not transfer.transaction_id:
        raise ValueError("شناسه تراکنش روی سند ثبت نشده است؛ تطبیق دستی لازم است.")

    client = TelegramAdsClient()
    status_payload = client.get_account_transaction_status(transfer.transaction_id)
    evidence = _parse_completed(status_payload, transfer=transfer)

    transfer.status = AccountFundingTransfer.Status.COMPLETED
    transfer.response_payload = {**(transfer.response_payload or {}), "reconciliation": evidence}
    transfer.confirmed_at = timezone.now()
    transfer.save(update_fields=["status", "response_payload", "confirmed_at", "updated_at"])
    AuditLog.objects.create(
        actor=actor,
        action="account_funding_transfer.reconciled",
        entity_type="account_funding_transfer",
        entity_id=transfer.pk,
        new_state=evidence,
    )
    return transfer