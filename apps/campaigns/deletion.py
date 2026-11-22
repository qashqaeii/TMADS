from __future__ import annotations

from django.db import transaction

from apps.campaigns.models import Campaign
from apps.finance.models import AdvertisingOrder, Payment, WalletLedgerEntry

_DELETABLE_CAMPAIGN_STATUSES = frozenset(
    {
        Campaign.Status.DRAFT,
        Campaign.Status.AWAITING_PAYMENT,
    }
)

_ORDER_BLOCKING = frozenset(
    {
        AdvertisingOrder.Status.PAYMENT_PENDING,
        AdvertisingOrder.Status.PAID,
        AdvertisingOrder.Status.READY_FOR_SUBMISSION,
        AdvertisingOrder.Status.SUBMITTING,
        AdvertisingOrder.Status.COMPLETED,
    }
)

_ORDER_CLEARABLE = frozenset(
    {
        AdvertisingOrder.Status.DRAFT,
        AdvertisingOrder.Status.AWAITING_PAYMENT,
        AdvertisingOrder.Status.CANCELLED,
        AdvertisingOrder.Status.FAILED,
    }
)

_PAYMENT_BLOCKING = frozenset(
    {
        Payment.Status.REDIRECTED,
        Payment.Status.VERIFIED,
    }
)


def can_delete_draft_campaign(campaign: Campaign) -> tuple[bool, str]:
    """حذف برای پیش‌نویس یا در انتظار پرداخت، بدون تعهد مالی قطعی."""
    if campaign.status not in _DELETABLE_CAMPAIGN_STATUSES:
        return False, "فقط کمپین‌های پیش‌نویس یا در انتظار پرداخت قابل حذف هستند."

    if campaign.remote_ads.exclude(remote_ad_id="").exists():
        return False, "تبلیغ متصل به تلگرام قابل حذف نیست."

    orders = list(AdvertisingOrder.objects.filter(campaign_id=campaign.id))
    if not orders:
        return True, ""

    order_ids = [order.id for order in orders]
    if any(order.status in _ORDER_BLOCKING for order in orders):
        return False, "برای این کمپین سفارش مالی ثبت شده؛ حذف ممکن نیست."

    if any(order.status not in _ORDER_CLEARABLE for order in orders):
        return False, "وضعیت سفارش مالی اجازه حذف نمی‌دهد."

    if Payment.objects.filter(order_id__in=order_ids, status__in=_PAYMENT_BLOCKING).exists():
        return False, "پرداخت در جریان یا ثبت‌شده است؛ حذف ممکن نیست."

    if WalletLedgerEntry.objects.filter(
        related_order_id__in=order_ids,
        entry_type=WalletLedgerEntry.EntryType.RESERVATION,
    ).exists():
        return False, "بودجهٔ رزروشده وجود دارد؛ ابتدا پرداخت/سفارش را بررسی کنید."

    return True, ""


@transaction.atomic
def delete_draft_campaign(campaign: Campaign) -> None:
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    ok, reason = can_delete_draft_campaign(campaign)
    if not ok:
        raise ValueError(reason)

    orders = list(
        AdvertisingOrder.objects.select_for_update().filter(campaign_id=campaign.id)
    )
    for order in orders:
        if order.status not in _ORDER_CLEARABLE:
            raise ValueError("پیش‌نویس دارای سابقه سفارش را حذف نکنید.")
        order.delete()

    campaign.delete()
