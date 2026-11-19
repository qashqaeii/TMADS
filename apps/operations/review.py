"""Authoritative internal review transitions for paid orders."""
from django.db import transaction

from apps.campaigns.models import Campaign, CampaignStatusHistory
from apps.finance.models import AdvertisingOrder, RefundRequest
from apps.finance.services import ensure_wallet, outstanding_order_reservation
from apps.notifications.services import notify_customer
from apps.policies.constants import FindingSeverity, POLICY_SUMMARY_VERSION, TMADS_TERMS_VERSION
from apps.policies.models import OpsPolicyReview
from apps.policies.services.policy_versions import get_active_policy_version
from apps.policies.services.preflight import CampaignPolicyPreflight


def review_payment_order(campaign, *, lock=False):
    if campaign.status not in {Campaign.Status.PENDING_REVIEW, Campaign.Status.READY_FOR_SUBMISSION}:
        raise ValueError("کمپین در صف قابل بررسی نیست.")
    if campaign.remote_ads.exclude(remote_ad_id="").exists():
        raise ValueError("کمپین قبلاً به تبلیغ تلگرام متصل شده است.")
    qs = AdvertisingOrder.objects.filter(campaign_id=campaign.id, customer=campaign.customer)
    if lock:
        qs = qs.select_for_update()
    rows = list(qs[:2])
    if len(rows) != 1 or rows[0].status != AdvertisingOrder.Status.PAID:
        raise ValueError("سفارش پرداخت‌شده و معتبر یافت نشد.")
    order = rows[0]
    if RefundRequest.objects.filter(order=order, status__in=[RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW, RefundRequest.Status.APPROVED]).exists():
        raise ValueError("درخواست بازپرداخت در جریان است.")
    wallet = ensure_wallet(campaign.customer)
    if order.total_irr <= 0 or outstanding_order_reservation(wallet, order.id) != order.total_irr:
        raise ValueError("رزرو سفارش نیازمند تطبیق مالی است.")
    return order


def accepted_current_terms(campaign):
    return campaign.policy_acceptances.filter(
        customer=campaign.customer,
        tmads_terms_version=TMADS_TERMS_VERSION,
        policy_summary_version=POLICY_SUMMARY_VERSION,
        policy_version=get_active_policy_version(),
    ).exists()


def require_recorded_approval(campaign):
    if not accepted_current_terms(campaign):
        raise ValueError("پذیرش نسخه فعلی قوانین توسط مشتری ثبت نشده است.")
    review = campaign.ops_policy_reviews.select_related("evaluation").first()
    if not review or review.decision != "approve" or review.policy_version_code != get_active_policy_version().code:
        raise ValueError("تأیید مستند اپراتور برای نسخه فعلی سیاست ثبت نشده است.")


@transaction.atomic
def review_campaign(campaign_id, *, actor, decision, reason="", internal_reason=""):
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
    review_payment_order(campaign, lock=True)
    if decision not in {"approve", "reject"}:
        raise ValueError("تصمیم نامعتبر است.")
    if decision == "approve":
        if not accepted_current_terms(campaign):
            raise ValueError("پذیرش نسخه فعلی قوانین توسط مشتری ثبت نشده است.")
        run = CampaignPolicyPreflight(campaign, actor=actor).run(strict=True, context="ops_approve", check_operator=False)
        if run.blocked:
            errors = [f.message_fa for f in run.findings if f.severity == FindingSeverity.BLOCKED]
            raise ValueError("؛ ".join(errors) or "تأیید ممکن نیست.")
        if run.needs_manual_review and not internal_reason.strip():
            raise ValueError("برای موارد نیازمند بررسی دستی، توضیح بررسی را وارد کنید.")
        reason = "کمپین پس از بررسی داخلی تأیید شد."
    else:
        reason = reason.strip()
        if not reason:
            raise ValueError("دلیل رد کمپین را برای مشتری بنویسید.")
    latest = CampaignPolicyPreflight.latest_evaluation(campaign)
    OpsPolicyReview.objects.create(
        campaign=campaign, evaluation=latest, reviewer=actor, decision=decision,
        reason_customer_fa=reason, reason_internal=internal_reason.strip(),
        policy_version_code=latest.policy_version.code if latest else get_active_policy_version().code,
    )
    previous = campaign.status
    campaign.status = Campaign.Status.READY_FOR_SUBMISSION if decision == "approve" else Campaign.Status.REJECTED
    campaign.save(update_fields=["status", "updated_at"])
    history = CampaignStatusHistory.objects.create(
        campaign=campaign, from_status=previous, to_status=campaign.status, note=reason,
    )
    notify_customer(campaign.customer,
        "کمپین تأیید شد" if decision == "approve" else "کمپین رد شد",
        reason, level="success" if decision == "approve" else "danger", related_campaign_id=campaign.id)
    if previous != campaign.status:
        from apps.notifications.sms import enqueue_sms
        enqueue_sms(campaign.customer, "campaign_status", f"campaign-review:{history.pk}",
                    {"status": "تأیید اولیه" if decision == "approve" else "رد شده"})
    return campaign
