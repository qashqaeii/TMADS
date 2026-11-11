from __future__ import annotations

from django.db import transaction

from apps.campaigns.models import Campaign, CampaignStatusHistory
from apps.core.models import AuditLog
from apps.notifications.services import notify_customer

from .models import AdvertisingOrder, RefundRequest
from .services import ensure_wallet, release_reservation_for_order


REFUNDABLE_CAMPAIGN_STATUSES = {
    Campaign.Status.PENDING_REVIEW,
    Campaign.Status.REJECTED,
    Campaign.Status.READY_FOR_SUBMISSION,
    Campaign.Status.AWAITING_PAYMENT,
}


def eligible_orders_for_refund(customer):
    return AdvertisingOrder.objects.filter(
        customer=customer,
        status=AdvertisingOrder.Status.PAID,
    ).order_by("-created_at")


def create_refund_request(*, customer, order: AdvertisingOrder, reason: str) -> RefundRequest:
    campaign = Campaign.objects.filter(id=order.campaign_id, customer=customer).first()
    if not campaign:
        raise ValueError("کمپین یافت نشد.")
    if order.status != AdvertisingOrder.Status.PAID:
        raise ValueError("فقط سفارش‌های پرداخت‌شده قابل بازپرداخت هستند.")
    if campaign.status not in REFUNDABLE_CAMPAIGN_STATUSES:
        raise ValueError("این کمپین در وضعیت فعال/ارسال‌شده قابل بازپرداخت خودکار نیست.")
    if RefundRequest.objects.filter(order=order, status__in=[RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW]).exists():
        raise ValueError("درخواست بازپرداخت باز برای این سفارش وجود دارد.")

    return RefundRequest.objects.create(
        customer=customer,
        order=order,
        amount_irr=order.total_irr,
        reason=reason.strip(),
        status=RefundRequest.Status.OPEN,
    )


@transaction.atomic
def approve_refund(refund: RefundRequest, *, actor) -> RefundRequest:
    if refund.status not in {RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW}:
        raise ValueError("درخواست در وضعیت قابل تأیید نیست.")

    order = refund.order
    campaign = Campaign.objects.select_for_update().get(id=order.campaign_id)
    wallet = ensure_wallet(refund.customer)

    release_reservation_for_order(
        wallet,
        refund.amount_irr,
        order.id,
        idempotency_key=f"refund-release-{refund.id}",
        description="بازپرداخت سفارش کمپین",
    )

    refund.status = RefundRequest.Status.PAID
    refund.save(update_fields=["status", "updated_at"])
    order.status = AdvertisingOrder.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])
    previous = campaign.status
    campaign.status = Campaign.Status.CANCELLED
    campaign.save(update_fields=["status", "updated_at"])
    CampaignStatusHistory.objects.create(
        campaign=campaign,
        from_status=previous,
        to_status=campaign.status,
        note="بازپرداخت تأیید شد",
    )
    AuditLog.objects.create(
        actor=actor,
        action="refund.approved",
        entity_type="refund",
        entity_id=refund.id,
        new_state={"order_id": str(order.id), "amount_irr": refund.amount_irr},
    )
    notify_customer(
        refund.customer,
        "بازپرداخت تأیید شد",
        "مبلغ رزرو به کیف پول شما بازگشت.",
        level="success",
        related_campaign_id=campaign.id,
    )
    return refund


def reject_refund(refund: RefundRequest, *, actor, note: str = "") -> RefundRequest:
    if refund.status not in {RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW}:
        raise ValueError("درخواست در وضعیت قابل رد نیست.")
    refund.status = RefundRequest.Status.REJECTED
    refund.reason = (refund.reason or "") + f"\n[رد اپراتور] {note}".strip()
    refund.save(update_fields=["status", "reason", "updated_at"])
    AuditLog.objects.create(
        actor=actor,
        action="refund.rejected",
        entity_type="refund",
        entity_id=refund.id,
    )
    notify_customer(
        refund.customer,
        "درخواست بازپرداخت رد شد",
        note or "با تیم پشتیبانی در ارتباط باشید.",
        level="warning",
    )
    return refund
