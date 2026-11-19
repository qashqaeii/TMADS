from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CustomerProfile
from apps.finance.invoice import issue_invoice_for_payment
from apps.finance.models import ExchangeRate, Payment, PlatformFeeRule, Wallet, WalletLedgerEntry


def ensure_wallet(customer: CustomerProfile) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(customer=customer)
    return wallet


@transaction.atomic
def credit_wallet_deposit(
    wallet: Wallet,
    amount_irr: int,
    idempotency_key: str,
    description: str = "",
) -> WalletLedgerEntry:
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if amount_irr <= 0:
        raise ValueError("مبلغ تراکنش باید مثبت باشد.")
    existing = WalletLedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if (existing.wallet_id != wallet.pk or existing.amount_irr != amount_irr
                or existing.entry_type != WalletLedgerEntry.EntryType.DEPOSIT
                or existing.related_order_id != None):
            raise ValueError("کلید تراکنش با عملیات مالی دیگری مرتبط است.")
        return existing

    wallet.available_irr += amount_irr
    wallet.save(update_fields=["available_irr", "updated_at"])

    return WalletLedgerEntry.objects.create(
        wallet=wallet,
        entry_type=WalletLedgerEntry.EntryType.DEPOSIT,
        amount_irr=amount_irr,
        balance_after_available=wallet.available_irr,
        balance_after_reserved=wallet.reserved_irr,
        idempotency_key=idempotency_key,
        description=description,
    )


@transaction.atomic
def reserve_for_order(wallet: Wallet, amount_irr: int, order_id: uuid.UUID, idempotency_key: str):
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if amount_irr <= 0:
        raise ValueError("مبلغ تراکنش باید مثبت باشد.")
    existing = WalletLedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if (existing.wallet_id != wallet.pk or existing.amount_irr != amount_irr
                or existing.entry_type != WalletLedgerEntry.EntryType.RESERVATION
                or existing.related_order_id != order_id):
            raise ValueError("کلید تراکنش با عملیات مالی دیگری مرتبط است.")
        return existing

    if wallet.available_irr < amount_irr:
        raise ValueError("موجودی کیف پول کافی نیست.")

    wallet.available_irr -= amount_irr
    wallet.reserved_irr += amount_irr
    wallet.save(update_fields=["available_irr", "reserved_irr", "updated_at"])

    return WalletLedgerEntry.objects.create(
        wallet=wallet,
        entry_type=WalletLedgerEntry.EntryType.RESERVATION,
        amount_irr=amount_irr,
        balance_after_available=wallet.available_irr,
        balance_after_reserved=wallet.reserved_irr,
        idempotency_key=idempotency_key,
        related_order_id=order_id,
        description="رزرو بودجه سفارش",
    )


@transaction.atomic
def release_reservation_for_order(
    wallet: Wallet,
    amount_irr: int,
    order_id: uuid.UUID,
    idempotency_key: str,
    *,
    description: str = "آزادسازی رزرو سفارش",
) -> WalletLedgerEntry:
    wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
    if amount_irr <= 0:
        raise ValueError("مبلغ تراکنش باید مثبت باشد.")
    existing = WalletLedgerEntry.objects.filter(idempotency_key=idempotency_key).first()
    if existing:
        if (existing.wallet_id != wallet.pk or existing.amount_irr != amount_irr
                or existing.entry_type != WalletLedgerEntry.EntryType.RESERVATION_RELEASE
                or existing.related_order_id != order_id):
            raise ValueError("کلید تراکنش با عملیات مالی دیگری مرتبط است.")
        return existing

    if wallet.reserved_irr < amount_irr or outstanding_order_reservation(wallet, order_id) < amount_irr:
        raise ValueError("مبلغ رزرو این سفارش کافی نیست.")

    wallet.reserved_irr -= amount_irr
    wallet.available_irr += amount_irr
    wallet.save(update_fields=["available_irr", "reserved_irr", "updated_at"])

    return WalletLedgerEntry.objects.create(
        wallet=wallet,
        entry_type=WalletLedgerEntry.EntryType.RESERVATION_RELEASE,
        amount_irr=amount_irr,
        balance_after_available=wallet.available_irr,
        balance_after_reserved=wallet.reserved_irr,
        idempotency_key=idempotency_key,
        related_order_id=order_id,
        description=description,
    )


def outstanding_order_reservation(wallet: Wallet, order_id: uuid.UUID) -> int:
    """Net reservation attributable to one order, not the wallet's pooled balance."""
    from django.db.models import Sum
    rows = wallet.ledger_entries.filter(related_order_id=order_id)
    def amount(kind):
        return rows.filter(entry_type=kind).aggregate(total=Sum("amount_irr"))["total"] or 0
    return (amount(WalletLedgerEntry.EntryType.RESERVATION)
            - amount(WalletLedgerEntry.EntryType.RESERVATION_RELEASE)
            - amount(WalletLedgerEntry.EntryType.CREDIT_ALLOCATION)
            - amount(WalletLedgerEntry.EntryType.SPEND)
            - amount(WalletLedgerEntry.EntryType.SERVICE_FEE))


def resolve_irr_per_ton() -> int:
    from apps.finance.exceptions import StaleRateError
    from apps.finance.services.ton_exchange_rate import get_pricing_snapshot, resolve_manual_snapshot

    manual = resolve_manual_snapshot()
    if manual:
        return manual.irr_per_ton
    try:
        snap = get_pricing_snapshot(require_fresh=False)
        return snap.irr_per_ton
    except StaleRateError:
        rate = ExchangeRate.objects.filter(is_active=True).order_by("-created_at").first()
        if rate and isinstance(rate.details, dict) and rate.details.get("irr_per_ton"):
            return int(rate.details["irr_per_ton"])
    except Exception:
        pass
    return int(settings.DEFAULT_EXCHANGE_RATE_TON_IRR or 0)


def ton_allocation_for_budget(advertising_budget_irr: int) -> Decimal:
    irr_per_ton = resolve_irr_per_ton()
    if irr_per_ton <= 0:
        return Decimal("0")
    return Decimal(advertising_budget_irr) / Decimal(irr_per_ton)


def active_platform_fee_percent() -> int:
    rule = PlatformFeeRule.objects.filter(is_active=True).order_by("-created_at").first()
    if rule:
        return int(rule.percent)
    return int(settings.PLATFORM_SERVICE_FEE_PERCENT)


def calculate_quote_totals(advertising_budget_irr: int) -> dict:
    from apps.finance.exceptions import PricingError
    from apps.finance.services.campaign_pricing import build_campaign_quote

    try:
        return build_campaign_quote(advertising_budget_irr)
    except PricingError:
        fee_percent = active_platform_fee_percent()
        service_fee = advertising_budget_irr * fee_percent // 100
        total = advertising_budget_irr + service_fee
        irr_per_ton = resolve_irr_per_ton()
        ton = ton_allocation_for_budget(advertising_budget_irr)
        return {
            "advertising_budget_irr": advertising_budget_irr,
            "service_fee_irr": service_fee,
            "total_irr": total,
            "fee_percent": fee_percent,
            "risk_buffer_irr": 0,
            "risk_buffer_percent": 0,
            "irr_per_ton": irr_per_ton,
            "ton_allocation": str(ton),
            "source": "fallback",
            "quote_status": "legacy",
        }


@transaction.atomic
def complete_topup_payment(payment: Payment, *, deposit_description: str = "شارژ کیف پول") -> bool:
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == Payment.Status.VERIFIED:
        return True
    if payment.amount_irr <= 0 or payment.order_id is not None:
        raise ValueError("پرداخت شارژ کیف پول نامعتبر است.")
    if payment.gateway == "zarinpal" and (not payment.provider_reference or payment.provider_amount_irr != payment.amount_irr):
        raise ValueError("مبلغ یا شناسه پرداخت نیازمند تطبیق است.")
    if payment.provider_reference and Payment.objects.filter(gateway=payment.gateway, provider_reference=payment.provider_reference).exclude(pk=payment.pk).exists():
        raise ValueError("شناسه پرداخت قبلاً ثبت شده است.")
    wallet = ensure_wallet(payment.customer)
    credit_wallet_deposit(
        wallet,
        payment.amount_irr,
        idempotency_key=f"payment-{payment.idempotency_key}",
        description=deposit_description,
    )
    issue_invoice_for_payment(payment, description=deposit_description)
    payment.status = Payment.Status.VERIFIED
    payment.save(update_fields=["status", "updated_at"])
    from apps.notifications.services import notify_customer

    notify_customer(
        payment.customer,
        "شارژ کیف پول موفق",
        "مبلغ به موجودی شما اضافه شد.",
        level="success",
    )
    return True


def verify_fake_payment(payment: Payment) -> bool:
    """Sandbox-only server-side verification."""
    if not settings.PAYMENT_FAKE_ENABLED or settings.APP_ENV.upper() == "PRODUCTION" or payment.gateway != "fake":
        return False
    return complete_topup_payment(payment, deposit_description="شارژ کیف پول (آزمایشی)")
