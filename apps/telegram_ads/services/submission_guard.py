"""Financial and state guard for central-account submission."""
from decimal import Decimal, InvalidOperation

from apps.campaigns.models import Campaign
from apps.finance.models import AdvertisingOrder, RefundRequest
from apps.finance.services import ensure_wallet, outstanding_order_reservation


def require_submission_order(campaign, *, claimed=False, lock=False):
    expected = Campaign.Status.SUBMITTING if claimed else Campaign.Status.READY_FOR_SUBMISSION
    if campaign.status != expected:
        raise ValueError("کمپین در وضعیت مجاز ارسال نیست.")
    if campaign.remote_ads.exclude(remote_ad_id="").exists():
        raise ValueError("تبلیغ قبلاً به تلگرام متصل شده است.")
    orders = AdvertisingOrder.objects.filter(campaign_id=campaign.id, customer=campaign.customer)
    if lock:
        orders = orders.select_for_update()
    rows = list(orders[:2])
    if len(rows) != 1:
        raise ValueError("سفارش یکتا برای کمپین یافت نشد.")
    order = rows[0]
    if order.status != (AdvertisingOrder.Status.SUBMITTING if claimed else AdvertisingOrder.Status.PAID):
        raise ValueError("وضعیت پرداخت سفارش برای ارسال معتبر نیست.")
    if RefundRequest.objects.filter(order=order, status__in=[RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW, RefundRequest.Status.APPROVED]).exists():
        raise ValueError("درخواست بازپرداخت در جریان است.")
    quote = getattr(order, "quote", None)
    data = quote.payload if quote else {}
    try:
        daily = Decimal(data["daily_limit_ton"])
        allocation = Decimal(str(data["ton_allocation"]))
        valid = (
            data.get("quote_status") == "locked" and bool(data.get("quote_nonce"))
            and quote.locked_total_irr == order.total_irr and order.total_irr > 0
            and allocation == order.ton_allocation and allocation > 0
            and allocation == allocation.quantize(Decimal("0.01"))
            and daily >= 0 and daily <= allocation and daily == daily.quantize(Decimal("0.01"))
            and data.get("requested_budget_irr") == campaign.budget_irr
            and data.get("requested_daily_cap_irr") == campaign.daily_cap_irr
        )
    except (KeyError, AttributeError, TypeError, InvalidOperation):
        valid = False
    if not valid:
        raise ValueError("پیش‌فاکتور پرداخت‌شده نیازمند تطبیق مالی است.")
    wallet = ensure_wallet(campaign.customer)
    if outstanding_order_reservation(wallet, order.id) != order.total_irr or wallet.reserved_irr < order.total_irr:
        raise ValueError("رزرو معتبر این سفارش یافت نشد.")
    return order
