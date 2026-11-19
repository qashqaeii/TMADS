"""Conservative allocation settlement. No Telegram write or remote-ID attachment."""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.campaigns.models import Campaign, CampaignStatusHistory
from apps.core.models import AuditLog
from apps.finance.models import AdvertisingOrder, Wallet, WalletLedgerEntry
from apps.finance.services import ensure_wallet, outstanding_order_reservation, release_reservation_for_order
from apps.notifications.services import notify_customer
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.models import APIRequestLog
from apps.telegram_ads.status_map import map_remote_status_to_campaign


def _verify_transfer(data, *, amount, claimed_at):
    """Only accept a complete history with one exact inbound account allocation.

    The API does not expose a unique transaction ID on AdTransaction. Refuse
    ambiguous histories instead of guessing which credit belongs to this order.
    """
    try:
        rows = data["transactions"]
        if not isinstance(rows, list) or data.get("next_offset") or data["total_count"] != len(rows):
            raise ValueError
        transfers = []
        for row in rows:
            peer = row["peer"]["type"]
            value = Decimal(str(row["amount"]))
            if row["currency"] != "TON" or not value.is_finite() or peer not in {"account", "views"}:
                raise ValueError
            if peer == "account":
                transfers.append((value, int(row["date"])))
            elif value > 0:
                raise ValueError
        if len(transfers) != 1:
            raise ValueError
        value, timestamp = transfers[0]
        if value != amount or not int(claimed_at.timestamp()) <= timestamp <= int(timezone.now().timestamp()) + 1:
            raise ValueError
        return {"amount_ton": str(value), "transaction_date": timestamp, "currency": "TON", "peer": "account"}
    except (TypeError, KeyError, ValueError, InvalidOperation, OverflowError):
        raise ValueError("سند تخصیص اعتبار کامل یا منطبق نیست؛ رزرو بدون تغییر باقی ماند.") from None


def _consume(wallet, order, amount, kind, suffix, description):
    if not amount:
        return
    if amount < 0 or wallet.reserved_irr < amount:
        raise ValueError("مبلغ رزرو سفارش نامعتبر است.")
    wallet.reserved_irr -= amount
    wallet.save(update_fields=["reserved_irr", "updated_at"])
    WalletLedgerEntry.objects.create(
        wallet=wallet, related_order_id=order.pk, entry_type=kind,
        amount_irr=amount, balance_after_available=wallet.available_irr,
        balance_after_reserved=wallet.reserved_irr,
        idempotency_key=f"settle-{order.pk}-{suffix}", description=description,
    )


@transaction.atomic
def settle_confirmed_allocation(campaign_id, *, actor):
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    orders = list(AdvertisingOrder.objects.select_for_update().filter(
        campaign_id=campaign.pk, customer=campaign.customer)[:2])
    if len(orders) != 1:
        raise ValueError("سفارش یکتا یافت نشد.")
    order = orders[0]
    if order.status == AdvertisingOrder.Status.COMPLETED:
        if WalletLedgerEntry.objects.filter(
            wallet__customer=campaign.customer, related_order_id=order.pk,
            idempotency_key=f"settle-{order.pk}-allocation",
            entry_type=WalletLedgerEntry.EntryType.CREDIT_ALLOCATION,
        ).exists():
            return order
        raise ValueError("سفارش قدیمی نیازمند تطبیق دستی است.")
    if order.status != AdvertisingOrder.Status.SUBMITTING:
        raise ValueError("سفارش در وضعیت قابل تسویه نیست.")
    ads = list(campaign.remote_ads.exclude(remote_ad_id="")[:2])
    if len(ads) != 1:
        raise ValueError("شناسه معتبر و یکتای تبلیغ ثبت نشده است.")
    ad = ads[0]
    receipt = APIRequestLog.objects.filter(
        operation="create_ad_receipt", success=True,
        meta__campaign_id=str(campaign.pk), meta__order_id=str(order.pk),
        meta__remote_ad_id=ad.remote_ad_id, meta__idempotency_key=f"tmads-create-{campaign.pk}",
    ).first()
    claim = campaign.status_history.filter(to_status=Campaign.Status.SUBMITTING).first()
    if not receipt or not claim or receipt.created_at < claim.created_at:
        raise ValueError("سند ایجاد تبلیغ ثبت نشده است؛ بررسی دستی لازم است.")
    quote = getattr(order, "quote", None)
    payload = quote.payload if quote else {}
    try:
        cost = payload["advertising_budget_irr"]
        fee = payload["service_fee_irr"]
        buffer = payload["risk_buffer_irr"]
        if (payload.get("quote_status") != "locked"
                or payload.get("buffer_disposition") != "return_after_confirmed_allocation"
                or not all(type(x) is int and x >= 0 for x in (cost, fee, buffer))
                or cost <= 0 or cost != order.advertising_budget_irr or fee != order.service_fee_irr
                or quote.locked_total_irr != order.total_irr or cost + fee + buffer != order.total_irr
                or Decimal(str(payload["ton_allocation"])) != order.ton_allocation or order.ton_allocation <= 0):
            raise ValueError
    except (KeyError, ValueError, TypeError, InvalidOperation):
        raise ValueError("شرایط مالی پیش‌فاکتور نیازمند تطبیق دستی است.") from None

    client = TelegramAdsClient()
    remote = client.get_ad(ad.remote_ad_id)
    if (str(remote.get("ad_id")) != ad.remote_ad_id or remote.get("currency") != "TON"
            or remote.get("promote_url") != campaign.destination):
        raise ValueError("هویت یا ارز تبلیغ با سند ایجاد آن یکسان نیست.")
    evidence = _verify_transfer(client.get_ad_transactions(ad.remote_ad_id, limit=100),
                                amount=order.ton_allocation, claimed_at=claim.created_at)

    wallet = Wallet.objects.select_for_update().get(pk=ensure_wallet(campaign.customer).pk)
    if outstanding_order_reservation(wallet, order.pk) != order.total_irr or wallet.reserved_irr < order.total_irr:
        raise ValueError("رزرو اختصاصی سفارش کامل نیست.")
    _consume(wallet, order, cost, WalletLedgerEntry.EntryType.CREDIT_ALLOCATION, "allocation", "تخصیص تأییدشده اعتبار تلگرام (نه مصرف نمایش)")
    _consume(wallet, order, fee, WalletLedgerEntry.EntryType.SERVICE_FEE, "fee", "کارمزد سفارش تبلیغ")
    if buffer:
        release_reservation_for_order(wallet, buffer, order.pk, f"settle-{order.pk}-buffer", description="بازگشت ذخیره موقت ریسک نرخ")
    order.status = AdvertisingOrder.Status.COMPLETED
    order.save(update_fields=["status", "updated_at"])
    ad.remote_status = str(remote.get("status") or "")
    ad.remote_status_raw = remote
    ad.save(update_fields=["remote_status", "remote_status_raw", "updated_at"])
    previous = campaign.status
    campaign.status = map_remote_status_to_campaign(remote)
    campaign.save(update_fields=["status", "updated_at"])
    CampaignStatusHistory.objects.create(campaign=campaign, from_status=previous,
        to_status=campaign.status, note="تخصیص اعتبار با سند تلگرام تطبیق و تسویه شد")
    AuditLog.objects.create(actor=actor, action="order.allocation_settled", entity_type="order", entity_id=order.pk,
        new_state={"remote_ad_id": ad.remote_ad_id, "evidence": evidence,
                   "allocation_cost_irr": cost, "service_fee_irr": fee, "returned_buffer_irr": buffer})
    notify_customer(campaign.customer, "تخصیص اعتبار تأیید شد",
        "اعتبار تبلیغاتی با تلگرام تطبیق داده شد و ذخیره موقت به کیف پول بازگشت.",
        level="success", related_campaign_id=campaign.pk)
    return order
