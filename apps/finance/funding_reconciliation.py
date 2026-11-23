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


def _parse_status(status_payload: dict, *, transfer: AccountFundingTransfer) -> dict:
    status = str(status_payload.get("status") or "").strip().lower()
    if status not in {"completed", "failed"}:
        raise ValueError("تراکنش هنوز کامل نشده یا وضعیت آن قابل تأیید نیست.")
    transaction_id = str(status_payload.get("transaction_id") or transfer.transaction_id or "").strip()
    if not transaction_id:
        raise ValueError("شناسه تراکنش در پاسخ تلگرام موجود نیست.")
    try:
        amount = Decimal(str(status_payload.get("amount")))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("مبلغ تراکنش قابل تأیید نیست.") from None
    if status == "completed" and (amount != transfer.amount or status_payload.get("currency") != transfer.currency):
        raise ValueError("مبلغ یا ارز تراکنش با سند انتقال مطابقت ندارد.")
    return {
        "status": status,
        "transaction_id": transaction_id,
        "amount": str(amount) if status == "completed" else str(transfer.amount),
        "currency": transfer.currency,
        "reconciled_at": timezone.now().isoformat(),
    }


def fetch_transfer_status_payload(transfer: AccountFundingTransfer) -> dict:
    if not transfer.transaction_id:
        raise ValueError("شناسه تراکنش روی سند ثبت نشده است؛ تطبیق دستی لازم است.")
    return TelegramAdsClient().get_account_transaction_status(transfer.transaction_id)


@transaction.atomic
def apply_reconciled_transfer(transfer_id, *, actor, evidence: dict) -> AccountFundingTransfer:
    _manager(actor)
    transfer = AccountFundingTransfer.objects.select_for_update().select_related(
        "connection", "operation__advertisement__campaign",
    ).get(pk=transfer_id)
    if transfer.status != AccountFundingTransfer.Status.UNCERTAIN:
        raise ValueError("فقط انتقال‌های نیازمند تطبیق قابل بررسی هستند.")

    if evidence["status"] == "completed":
        transfer.status = AccountFundingTransfer.Status.COMPLETED
        transfer.transaction_id = evidence["transaction_id"]
        transfer.confirmed_at = timezone.now()
    else:
        transfer.status = AccountFundingTransfer.Status.FAILED
        if transfer.operation_id and transfer.operation.action == "increase_budget":
            from apps.finance.managed_budget_increase import release_managed_budget_reservation

            campaign = transfer.operation.advertisement.campaign
            release_managed_budget_reservation(campaign.customer, transfer.operation_id)

    transfer.response_payload = {**(transfer.response_payload or {}), "reconciliation": evidence}
    transfer.save(update_fields=["status", "transaction_id", "response_payload", "confirmed_at", "updated_at"])
    AuditLog.objects.create(
        actor=actor,
        action="account_funding_transfer.reconciled",
        entity_type="account_funding_transfer",
        entity_id=transfer.pk,
        new_state=evidence,
    )
    return transfer


def reconcile_uncertain_funding_transfer(transfer_id, *, actor) -> AccountFundingTransfer:
    _manager(actor)
    transfer = AccountFundingTransfer.objects.select_related("connection").get(pk=transfer_id)
    if transfer.status != AccountFundingTransfer.Status.UNCERTAIN:
        raise ValueError("فقط انتقال‌های نیازمند تطبیق قابل بررسی هستند.")
    evidence = _parse_status(fetch_transfer_status_payload(transfer), transfer=transfer)
    return apply_reconciled_transfer(transfer_id, actor=actor, evidence=evidence)