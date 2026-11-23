"""Wallet reserve, platform funding and ledger settlement for managed budget increases."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction

from apps.finance.models import Wallet, WalletLedgerEntry
from apps.finance.services import ensure_wallet
from apps.finance.services.campaign_pricing import quote_expired


@dataclass(frozen=True)
class ManagedBudgetQuote:
    cost: int
    fee: int
    buffer: int
    total: int
    ton: Decimal


def parse_managed_increase_quote(request_payload: dict) -> ManagedBudgetQuote:
    quote = request_payload.get("quote") or {}
    if quote_expired(quote):
        raise ValueError("اعتبار پیش‌فاکتور به پایان رسیده است.")
    try:
        cost = int(quote["advertising_budget_irr"])
        fee = int(quote["service_fee_irr"])
        buffer = int(quote["risk_buffer_irr"])
        total = int(quote["total_irr"])
        ton = Decimal(str(quote["ton_allocation"]))
        amount_ton = Decimal(str(request_payload["amount_ton"]))
        if (
            quote.get("quote_status") != "locked"
            or cost <= 0
            or not all(x >= 0 for x in (cost, fee, buffer))
            or total != cost + fee + buffer
            or not ton.is_finite()
            or ton <= 0
            or amount_ton != ton
        ):
            raise ValueError
    except (KeyError, ValueError, TypeError, InvalidOperation):
        raise ValueError("شرایط مالی پیش‌فاکتور معتبر نیست.") from None
    return ManagedBudgetQuote(cost=cost, fee=fee, buffer=buffer, total=total, ton=ton)


def _reserve_key(op_id) -> str:
    return f"budget-{op_id}-reserve"


def outstanding_budget_reservation(wallet: Wallet, op_id) -> int:
    if WalletLedgerEntry.objects.filter(
        wallet=wallet,
        idempotency_key=f"budget-{op_id}-allocation",
        entry_type=WalletLedgerEntry.EntryType.CREDIT_ALLOCATION,
    ).exists():
        return 0
    row = WalletLedgerEntry.objects.filter(
        wallet=wallet,
        idempotency_key=_reserve_key(op_id),
        entry_type=WalletLedgerEntry.EntryType.RESERVATION,
    ).first()
    return row.amount_irr if row else 0


def _consume(wallet, op_id, amount, kind, suffix, description):
    if not amount:
        return
    if amount < 0 or wallet.reserved_irr < amount:
        raise ValueError("مبلغ رزرو عملیات بودجه نامعتبر است.")
    wallet.reserved_irr -= amount
    wallet.save(update_fields=["reserved_irr", "updated_at"])
    WalletLedgerEntry.objects.create(
        wallet=wallet,
        entry_type=kind,
        amount_irr=amount,
        balance_after_available=wallet.available_irr,
        balance_after_reserved=wallet.reserved_irr,
        idempotency_key=f"budget-{op_id}-{suffix}",
        description=description,
    )


@transaction.atomic
def reserve_managed_budget_increase(customer, op_id: int, total_irr: int) -> None:
    wallet = Wallet.objects.select_for_update().get(pk=ensure_wallet(customer).pk)
    key = _reserve_key(op_id)
    existing = WalletLedgerEntry.objects.filter(idempotency_key=key).first()
    if existing:
        if existing.amount_irr != total_irr or existing.wallet_id != wallet.pk:
            raise ValueError("رزرو قبلی با مبلغ فعلی مطابقت ندارد.")
        return
    if total_irr <= 0 or wallet.available_irr < total_irr:
        raise ValueError("موجودی کیف پول برای افزایش بودجه کافی نیست.")
    wallet.available_irr -= total_irr
    wallet.reserved_irr += total_irr
    wallet.save(update_fields=["available_irr", "reserved_irr", "updated_at"])
    WalletLedgerEntry.objects.create(
        wallet=wallet,
        entry_type=WalletLedgerEntry.EntryType.RESERVATION,
        amount_irr=total_irr,
        balance_after_available=wallet.available_irr,
        balance_after_reserved=wallet.reserved_irr,
        idempotency_key=key,
        description="رزرو افزایش بودجه تبلیغ (مدیریت‌شده)",
    )


@transaction.atomic
def settle_managed_budget_increase(customer, op_id: int, quote: ManagedBudgetQuote) -> None:
    wallet = Wallet.objects.select_for_update().get(pk=ensure_wallet(customer).pk)
    if outstanding_budget_reservation(wallet, op_id) != quote.total:
        raise ValueError("رزرو عملیات بودجه کامل نیست.")
    _consume(
        wallet, op_id, quote.cost,
        WalletLedgerEntry.EntryType.CREDIT_ALLOCATION,
        "allocation",
        "تخصیص افزایش بودجه تبلیغ (نه مصرف نمایش)",
    )
    _consume(wallet, op_id, quote.fee, WalletLedgerEntry.EntryType.SERVICE_FEE, "fee", "کارمزد افزایش بودجه")
    if quote.buffer:
        if wallet.reserved_irr < quote.buffer:
            raise ValueError("ذخیره ریسک قابل بازگشت نیست.")
        wallet.reserved_irr -= quote.buffer
        wallet.available_irr += quote.buffer
        wallet.save(update_fields=["available_irr", "reserved_irr", "updated_at"])
        WalletLedgerEntry.objects.create(
            wallet=wallet,
            entry_type=WalletLedgerEntry.EntryType.RESERVATION_RELEASE,
            amount_irr=quote.buffer,
            balance_after_available=wallet.available_irr,
            balance_after_reserved=wallet.reserved_irr,
            idempotency_key=f"budget-{op_id}-buffer",
            description="بازگشت ذخیره موقت ریسک نرخ (افزایش بودجه)",
        )


@transaction.atomic
def release_managed_budget_reservation(customer, op_id: int, *, amount_irr: int | None = None) -> None:
    """Release an unused reservation after a rejected or failed managed increase."""
    wallet = Wallet.objects.select_for_update().get(pk=ensure_wallet(customer).pk)
    reserved = outstanding_budget_reservation(wallet, op_id)
    if not reserved:
        return
    release_amount = reserved if amount_irr is None else amount_irr
    if release_amount <= 0 or release_amount > reserved:
        raise ValueError("مبلغ آزادسازی رزرو نامعتبر است.")
    wallet.reserved_irr -= release_amount
    wallet.available_irr += release_amount
    wallet.save(update_fields=["available_irr", "reserved_irr", "updated_at"])
    WalletLedgerEntry.objects.create(
        wallet=wallet,
        entry_type=WalletLedgerEntry.EntryType.RESERVATION_RELEASE,
        amount_irr=release_amount,
        balance_after_available=wallet.available_irr,
        balance_after_reserved=wallet.reserved_irr,
        idempotency_key=f"budget-{op_id}-release",
        description="آزادسازی رزرو افزایش بودجه لغو‌شده",
    )