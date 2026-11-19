from __future__ import annotations

from django.db import transaction
from django.db.models import Exists, OuterRef

from apps.campaigns.models import Campaign, CampaignStatusHistory
from apps.core.models import AuditLog
from apps.notifications.services import notify_customer

from .models import AdvertisingOrder, RefundRequest
from .services import ensure_wallet, outstanding_order_reservation, release_reservation_for_order


REFUNDABLE_CAMPAIGN_STATUSES = {
    Campaign.Status.PENDING_REVIEW,
    Campaign.Status.REJECTED,
    Campaign.Status.READY_FOR_SUBMISSION,
    Campaign.Status.AWAITING_PAYMENT,
}


def eligible_orders_for_refund(customer):
    eligible_campaigns = Campaign.objects.filter(pk=OuterRef("campaign_id"), customer=customer,
        status__in=REFUNDABLE_CAMPAIGN_STATUSES).exclude(remote_ads__remote_ad_id__gt="")
    open_requests = RefundRequest.objects.filter(order_id=OuterRef("pk"),
        status__in=[RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW, RefundRequest.Status.APPROVED])
    return AdvertisingOrder.objects.filter(customer=customer, status=AdvertisingOrder.Status.PAID).filter(
        Exists(eligible_campaigns), ~Exists(open_requests)).order_by("-created_at")


@transaction.atomic
def create_refund_request(*, customer, order: AdvertisingOrder, reason: str) -> RefundRequest:
    campaign = Campaign.objects.select_for_update().filter(id=order.campaign_id, customer=customer).first()
    order = AdvertisingOrder.objects.select_for_update().get(pk=order.pk, customer=customer)
    if not campaign:
        raise ValueError("کمپین یافت نشد.")
    if order.status != AdvertisingOrder.Status.PAID:
        raise ValueError("فقط سفارش‌های پرداخت‌شده قابل بازپرداخت هستند.")
    if campaign.status not in REFUNDABLE_CAMPAIGN_STATUSES or campaign.remote_ads.exclude(remote_ad_id="").exists():
        raise ValueError("این کمپین در وضعیت فعال/ارسال‌شده قابل بازپرداخت خودکار نیست.")
    if outstanding_order_reservation(ensure_wallet(customer), order.id) != order.total_irr or order.total_irr <= 0:
        raise ValueError("رزرو مالی سفارش نیازمند تطبیق است.")
    if RefundRequest.objects.filter(order=order, status__in=[RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW, RefundRequest.Status.APPROVED]).exists():
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
    campaign = Campaign.objects.select_for_update().get(id=refund.order.campaign_id, customer=refund.customer)
    order = AdvertisingOrder.objects.select_for_update().get(pk=refund.order_id, customer=refund.customer)
    refund.refresh_from_db()
    if refund.status not in {RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW}:
        raise ValueError("درخواست در وضعیت قابل تأیید نیست.")
    if (order.status != AdvertisingOrder.Status.PAID or campaign.status not in REFUNDABLE_CAMPAIGN_STATUSES
            or campaign.remote_ads.exclude(remote_ad_id="").exists() or refund.amount_irr != order.total_irr):
        raise ValueError("وضعیت سفارش تغییر کرده؛ بازپرداخت خودکار مجاز نیست.")
    wallet = ensure_wallet(refund.customer)
    if outstanding_order_reservation(wallet, order.id) != refund.amount_irr or refund.amount_irr <= 0:
        raise ValueError("رزرو مالی این سفارش نیازمند تطبیق است.")

    release_reservation_for_order(
        wallet,
        refund.amount_irr,
        order.id,
        idempotency_key=f"refund-release-order-{order.id}",
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


@transaction.atomic
def reject_refund(refund: RefundRequest, *, actor, note: str = "") -> RefundRequest:
    Campaign.objects.select_for_update().get(id=refund.order.campaign_id, customer=refund.customer)
    AdvertisingOrder.objects.select_for_update().get(pk=refund.order_id, customer=refund.customer)
    refund.refresh_from_db()
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


@transaction.atomic
def mark_refund_in_review(refund: RefundRequest, *, actor):
    Campaign.objects.select_for_update().get(id=refund.order.campaign_id, customer=refund.customer)
    AdvertisingOrder.objects.select_for_update().get(pk=refund.order_id, customer=refund.customer)
    refund.refresh_from_db()
    if refund.status != RefundRequest.Status.OPEN:
        raise ValueError("فقط درخواست باز قابل انتقال به بررسی است.")
    refund.status = RefundRequest.Status.REVIEW
    refund.save(update_fields=["status", "updated_at"])
    AuditLog.objects.create(actor=actor, action="refund.review", entity_type="refund", entity_id=refund.pk)
    return refund
