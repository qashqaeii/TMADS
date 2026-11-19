from __future__ import annotations

from django.db import transaction

from apps.campaigns.models import Campaign
from apps.finance.models import AdvertisingOrder, WalletLedgerEntry

_ORDER_BLOCKING = frozenset(
    {
        AdvertisingOrder.Status.PAID,
        AdvertisingOrder.Status.READY_FOR_SUBMISSION,
        AdvertisingOrder.Status.SUBMITTING,
        AdvertisingOrder.Status.COMPLETED,
    }
)


def can_delete_draft_campaign(campaign: Campaign) -> tuple[bool, str]:
    """حذف فقط برای پیش‌نویس بدون سفارش پرداخت‌شده یا رزرو."""
    if campaign.status != Campaign.Status.DRAFT:
        return False, "فقط کمپین‌های پیش‌نویس قابل حذف هستند."

    if campaign.remote_ads.exclude(remote_ad_id="").exists():
        return False, "تبلیغ متصل به تلگرام قابل حذف نیست."

    order_ids = list(
        AdvertisingOrder.objects.filter(campaign_id=campaign.id).values_list("id", flat=True)
    )
    if not order_ids:
        return True, ""

    if AdvertisingOrder.objects.filter(
        campaign_id=campaign.id,
        status__in=_ORDER_BLOCKING,
    ).exists():
        return False, "برای این کمپین سفارش مالی ثبت شده؛ حذف ممکن نیست."

    if WalletLedgerEntry.objects.filter(
        related_order_id__in=order_ids,
        entry_type=WalletLedgerEntry.EntryType.RESERVATION,
    ).exists():
        return False, "بودجهٔ رزروشده وجود دارد؛ ابتدا پرداخت/سفارش را بررسی کنید."

    return False, "پیش‌نویس دارای سابقه سفارش مالی است."


@transaction.atomic
def delete_draft_campaign(campaign: Campaign) -> None:
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    ok, _reason = can_delete_draft_campaign(campaign)
    if not ok:
        raise ValueError(_reason)
    # Preserve financial order records; deletion is only for unused drafts.
    if AdvertisingOrder.objects.filter(campaign_id=campaign.id).exists():
        raise ValueError("پیش‌نویس دارای سابقه سفارش را حذف نکنید.")
    campaign.delete()
