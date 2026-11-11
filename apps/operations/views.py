from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.models import CustomerProfile
from apps.accounts.permissions import staff_ops_required
from apps.campaigns.models import Campaign, CampaignStatusHistory, TelegramAdvertisement
from apps.core.models import AuditLog
from apps.finance.models import AdvertisingOrder, ExchangeRate, RefundRequest, Wallet
from apps.finance.refunds import approve_refund, reject_refund
from apps.notifications.services import notify_customer
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.submission import submit_campaign_to_telegram
from apps.telegram_ads.models import APICapability, APIRequestLog


@login_required
@staff_ops_required
def overview(request):
    return render(
        request,
        "operations/overview.html",
        {
            "customer_count": CustomerProfile.objects.count(),
            "order_count": AdvertisingOrder.objects.count(),
            "pending_campaigns": Campaign.objects.filter(
                status=Campaign.Status.PENDING_REVIEW,
            ).count(),
            "open_refunds": RefundRequest.objects.filter(
                status__in=[RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW],
            ).count(),
            "wallet_liabilities": Wallet.objects.aggregate(
                available=Sum("available_irr"),
                reserved=Sum("reserved_irr"),
            ),
        },
    )


@login_required
@staff_ops_required
def campaign_ops(request):
    status = request.GET.get("status", Campaign.Status.PENDING_REVIEW)
    campaigns = Campaign.objects.select_related("customer", "customer__user").order_by("-updated_at")
    if status and status != "all":
        campaigns = campaigns.filter(status=status)
    elif status == "all":
        status = ""
    return render(
        request,
        "operations/campaigns.html",
        {"campaigns": campaigns[:80], "filter_status": status},
    )


@login_required
@staff_ops_required
def campaign_review(request, campaign_id):
    campaign = get_object_or_404(Campaign.objects.select_related("customer"), id=campaign_id)
    order = AdvertisingOrder.objects.filter(campaign_id=campaign.id).first()
    creative = campaign.creatives.first()
    remote_ads = campaign.remote_ads.all()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "rerun_policy":
            from apps.policies.services.preflight import CampaignPolicyPreflight

            run = CampaignPolicyPreflight(campaign, actor=request.user).run(
                strict=True,
                context="ops_rerun",
                check_operator=True,
            )
            if run.blocked:
                messages.warning(request, "پیش‌پرواز سیاست: موارد مسدودکننده وجود دارد.")
            else:
                messages.success(request, "اعتبارسنجی سیاست دوباره اجرا شد.")
        elif action == "approve":
            from apps.policies.constants import FindingSeverity
            from apps.policies.services.preflight import CampaignPolicyPreflight

            run = CampaignPolicyPreflight(campaign, actor=request.user).run(
                strict=True,
                context="ops_approve",
                check_operator=False,
            )
            if run.blocked:
                blocked = [f.message_fa for f in run.findings if f.severity == FindingSeverity.BLOCKED]
                messages.error(
                    request,
                    blocked[0] if blocked else "تأیید ممکن نیست: نقض سیاست قطعی.",
                )
                return redirect("operations:campaign_review", campaign_id=campaign.id)
            campaign.status = Campaign.Status.READY_FOR_SUBMISSION
            campaign.save(update_fields=["status", "updated_at"])
            CampaignStatusHistory.objects.create(
                campaign=campaign,
                to_status=campaign.status,
                note="تأیید داخلی",
            )
            notify_customer(
                campaign.customer,
                "کمپین تأیید شد",
                "کمپین شما آماده ارسال به Telegram Ads است.",
                level="success",
                related_campaign_id=campaign.id,
            )
            messages.success(request, "کمپین تأیید شد.")
        elif action == "reject":
            reason = request.POST.get("reason", "").strip() or "نیاز به اصلاح محتوا"
            from apps.policies.models import OpsPolicyReview
            from apps.policies.services.preflight import CampaignPolicyPreflight

            latest = CampaignPolicyPreflight.latest_evaluation(campaign)
            OpsPolicyReview.objects.create(
                campaign=campaign,
                evaluation=latest,
                reviewer=request.user,
                decision="reject",
                reason_customer_fa=reason,
                reason_internal=request.POST.get("reason_internal", "").strip(),
                policy_version_code=latest.policy_version.code if latest else "",
            )
            campaign.status = Campaign.Status.REJECTED
            campaign.save(update_fields=["status", "updated_at"])
            CampaignStatusHistory.objects.create(
                campaign=campaign,
                to_status=campaign.status,
                note=reason,
            )
            notify_customer(
                campaign.customer,
                "کمپین رد شد",
                reason,
                level="danger",
                related_campaign_id=campaign.id,
            )
            messages.warning(request, "کمپین رد شد.")
        elif action == "submit_telegram":
            try:
                submit_campaign_to_telegram(campaign)
                messages.success(request, "ارسال به Telegram Ads انجام شد (در صورت فعال بودن write).")
            except TelegramAdsError as exc:
                messages.error(request, str(exc))
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == "link_ad":
            remote_id = request.POST.get("remote_ad_id", "").strip()
            if remote_id:
                ad, _ = TelegramAdvertisement.objects.get_or_create(campaign=campaign)
                ad.remote_ad_id = remote_id
                ad.save(update_fields=["remote_ad_id", "updated_at"])
                messages.success(request, "شناسه تبلیغ متصل شد.")
        AuditLog.objects.create(
            actor=request.user,
            action=f"ops.{action}",
            entity_type="campaign",
            entity_id=campaign.id,
        )
        return redirect("operations:campaign_review", campaign_id=campaign.id)

    from apps.telegram_ads.services.ad_write import dry_run_create_ad

    preflight = None
    try:
        preflight = dry_run_create_ad(campaign)
    except Exception as exc:
        preflight = {"ok": False, "errors": [str(exc)]}

    from apps.policies.models import OperatorAdvertisingAuthorization
    from apps.policies.services.preflight import CampaignPolicyPreflight

    policy_run = CampaignPolicyPreflight(campaign).run(
        strict=True,
        persist=False,
        context="ops_review",
        check_operator=True,
    )
    operator_gate = OperatorAdvertisingAuthorization.objects.filter(is_current=True).first()

    return render(
        request,
        "operations/campaign_review.html",
        {
            "campaign": campaign,
            "order": order,
            "creative": creative,
            "remote_ads": remote_ads,
            "preflight": preflight,
            "policy_run": policy_run,
            "operator_gate": operator_gate,
        },
    )


@login_required
@staff_ops_required
def exchange_rates(request):
    from django.utils import timezone as tz

    from apps.finance.services.ton_exchange_rate import fetch_live_snapshot, get_cached_snapshot

    rates = ExchangeRate.objects.order_by("-created_at")[:30]
    live = get_cached_snapshot(allow_stale_display=True)
    action = request.POST.get("action") if request.method == "POST" else ""
    if request.method == "POST" and action == "refresh_nobitex":
        try:
            live = fetch_live_snapshot(persist=True)
            messages.success(request, "نرخ نوبیتکس بروزرسانی شد (فقط خواندن).")
        except Exception as exc:
            messages.error(request, f"نوبیتکس: {exc}")
        return redirect("operations:exchange_rates")
    if request.method == "POST" and action == "manual":
        reason = request.POST.get("reason", "").strip()[:200]
        try:
            irr_per_ton = int(request.POST.get("irr_per_ton", "0"))
        except ValueError:
            irr_per_ton = 0
        if irr_per_ton <= 0:
            messages.error(request, "نرخ دستی نامعتبر است.")
            return redirect("operations:exchange_rates")
        ExchangeRate.objects.filter(is_active=True, source="manual").update(is_active=False)
        now = tz.now()
        ExchangeRate.objects.create(
            ton_per_irr=Decimal(1) / Decimal(irr_per_ton),
            source="manual",
            is_active=True,
            details={
                "irr_per_ton": irr_per_ton,
                "best_ask_irr": str(irr_per_ton),
                "fetched_at": now.isoformat(),
                "manual_reason": reason,
                "manual_expires_at": (now + tz.timedelta(hours=24)).isoformat(),
                "source": "manual",
                "market_symbol": "manual",
                "stats_pair": "manual",
            },
        )
        AuditLog.objects.create(
            actor=request.user,
            action="exchange_rate.manual",
            entity_type="ExchangeRate",
            new_state={"irr_per_ton": irr_per_ton, "reason": reason},
        )
        messages.success(request, "نرخ دستی ثبت شد (اولویت بر نوبیتکس تا انقضا).")
        return redirect("operations:exchange_rates")
    return render(
        request,
        "operations/exchange_rates.html",
        {
            "rates": rates,
            "live_rate": live,
            "fee_percent": settings.PLATFORM_SERVICE_FEE_PERCENT,
            "buffer_percent": settings.TON_PRICING_RISK_BUFFER_PERCENT,
        },
    )


@login_required
@staff_ops_required
def api_status(request):
    account = None
    error = None
    capabilities = APICapability.objects.order_by("feature_key")
    try:
        account = TelegramAdsClient().get_account()
    except TelegramAdsError as exc:
        error = str(exc)

    last_ok = APIRequestLog.objects.filter(success=True).order_by("-created_at").first()
    last_fail = APIRequestLog.objects.filter(success=False).order_by("-created_at").first()

    return render(
        request,
        "operations/api_status.html",
        {
            "account": account,
            "error": error,
            "last_ok": last_ok,
            "last_fail": last_fail,
            "capabilities": capabilities,
        },
    )


@login_required
@staff_ops_required
def audit_logs(request):
    logs = AuditLog.objects.select_related("actor").order_by("-created_at")[:100]
    return render(request, "operations/audit_logs.html", {"logs": logs})


@login_required
@staff_ops_required
def refunds_ops(request):
    refunds = (
        RefundRequest.objects.select_related("customer", "order")
        .order_by("-created_at")[:80]
    )
    status = request.GET.get("status", "")
    if status:
        refunds = refunds.filter(status=status)

    if request.method == "POST":
        refund_id = request.POST.get("refund_id")
        action = request.POST.get("action")
        refund = get_object_or_404(RefundRequest, id=refund_id)
        try:
            if action == "approve":
                approve_refund(refund, actor=request.user)
                messages.success(request, "بازپرداخت تأیید و مبلغ به کیف پول مشتری بازگشت.")
            elif action == "reject":
                reject_refund(refund, actor=request.user, note=request.POST.get("note", "").strip())
                messages.warning(request, "درخواست بازپرداخت رد شد.")
            elif action == "review":
                refund.status = RefundRequest.Status.REVIEW
                refund.save(update_fields=["status", "updated_at"])
                messages.info(request, "در حال بررسی علامت‌گذاری شد.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("operations:refunds")

    return render(
        request,
        "operations/refunds.html",
        {"refunds": refunds, "filter_status": status},
    )
