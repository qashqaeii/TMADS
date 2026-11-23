from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from apps.accounts.models import CustomerProfile
from apps.accounts.permissions import staff_ops_required
from apps.campaigns.models import Campaign, CampaignStatusHistory, TelegramAdvertisement, RemoteAdOperation
from apps.core.models import AuditLog
from django.utils import timezone
from apps.finance.models import AccountFundingTransfer, AdvertisingOrder, ExchangeRate, RefundRequest, Wallet
from apps.finance.refunds import approve_refund, reject_refund, mark_refund_in_review
from apps.notifications.services import notify_customer
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.submission import submit_campaign_to_telegram
from apps.telegram_ads.models import APICapability, APIRequestLog
from apps.operations.review import review_campaign, review_payment_order
from apps.telegram_ads.services.submission_guard import require_submission_order


def _telegram_ads_treasury():
    """Read-only central Telegram Ads balance with optional Toman estimate."""
    from apps.finance.services.money import irr_to_toman_int
    from apps.finance.services.ton_equiv import resolve_ton_display_rate, ton_amount_to_irr

    snapshot = {
        "ok": False,
        "error": "",
        "title": "",
        "account_id": "",
        "currency": "",
        "remaining": None,
        "spent": None,
        "ads_budget": None,
        "remaining_toman": None,
        "spent_toman": None,
        "irr_per_ton": None,
        "rate_hint": "",
    }
    try:
        account = TelegramAdsClient().get_account() or {}
    except TelegramAdsError:
        snapshot["error"] = "خواندن موجودی حساب تلگرام ادز ممکن نشد."
        return snapshot
    except Exception:
        snapshot["error"] = "ارتباط با سرویس تلگرام ادز برقرار نشد."
        return snapshot

    currency = str(account.get("currency") or "").upper()
    remaining = account.get("remaining_budget")
    spent = account.get("spent_budget")
    ads_budget = account.get("ads_budget")
    irr_per_ton, rate_hint = resolve_ton_display_rate()
    remaining_toman = spent_toman = None
    if currency == "TON" and irr_per_ton:
        rem_irr = ton_amount_to_irr(remaining, irr_per_ton)
        spent_irr = ton_amount_to_irr(spent, irr_per_ton)
        if rem_irr is not None:
            remaining_toman = irr_to_toman_int(rem_irr)
        if spent_irr is not None:
            spent_toman = irr_to_toman_int(spent_irr)

    snapshot.update(
        {
            "ok": True,
            "title": str(account.get("title") or "").strip(),
            "account_id": str(account.get("account_id") or "").strip(),
            "currency": currency,
            "remaining": remaining,
            "spent": spent,
            "ads_budget": ads_budget,
            "remaining_toman": remaining_toman,
            "spent_toman": spent_toman,
            "irr_per_ton": irr_per_ton if currency == "TON" else None,
            "rate_hint": rate_hint if currency == "TON" and irr_per_ton else "",
        }
    )
    return snapshot


@login_required
@staff_ops_required
def overview(request):
    return render(
        request,
        "operations/overview.html",
        {
            "today": timezone.localdate(),
            "remote_pending": RemoteAdOperation.objects.filter(status=RemoteAdOperation.Status.PENDING).count(),
            "customer_count": CustomerProfile.objects.count(),
            "order_count": AdvertisingOrder.objects.count(),
            "pending_campaigns": Campaign.objects.filter(
                status=Campaign.Status.PENDING_REVIEW,
            ).count(),
            "open_refunds": RefundRequest.objects.filter(
                status__in=[RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW],
            ).count(),
            "uncertain_funding": AccountFundingTransfer.objects.filter(
                status=AccountFundingTransfer.Status.UNCERTAIN,
            ).count(),
            "wallet_liabilities": Wallet.objects.aggregate(
                available=Sum("available_irr"),
                reserved=Sum("reserved_irr"),
            ),
            "ads_treasury": _telegram_ads_treasury(),
        },
    )


@login_required
@staff_ops_required
def campaign_ops(request):
    from django.core.paginator import Paginator
    from django.db.models import Q

    status = request.GET.get("status", Campaign.Status.PENDING_REVIEW)
    if status not in Campaign.Status.values and status != "all":
        status = Campaign.Status.PENDING_REVIEW
    query = request.GET.get("q", "").strip()[:100]
    campaigns = Campaign.objects.select_related("customer", "customer__user").order_by("-updated_at", "-id")
    if status != "all":
        campaigns = campaigns.filter(status=status)
    if query:
        campaigns = campaigns.filter(
            Q(name__icontains=query) | Q(customer__display_name__icontains=query)
            | Q(customer__company_name__icontains=query) | Q(customer__user__username__icontains=query)
        )
    page_obj = Paginator(campaigns, 25).get_page(request.GET.get("page"))
    return render(
        request, "operations/campaigns.html",
        {"campaigns": page_obj.object_list, "page_obj": page_obj,
         "filter_status": "" if status == "all" else status,
         "query": query, "total_results": page_obj.paginator.count,
         "status_choices": Campaign.Status.choices},
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
        elif action in {"approve", "reject"}:
            try:
                review_campaign(
                    campaign.id, actor=request.user, decision=action,
                    reason=request.POST.get("reason", ""), internal_reason=request.POST.get("reason_internal", ""),
                )
                messages.success(request, "تصمیم بررسی کمپین ثبت شد.")
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == "submit_telegram":
            try:
                submit_campaign_to_telegram(campaign)
                messages.success(request, "شناسه تبلیغ دریافت شد؛ تسویه مالی پس از تطبیق ثبت می‌شود.")
            except TelegramAdsError as exc:
                messages.error(request, str(exc))
            except ValueError as exc:
                messages.error(request, str(exc))
        elif action == "settle_allocation":
            from apps.finance.settlement import settle_confirmed_allocation
            try:
                settle_confirmed_allocation(campaign.pk, actor=request.user)
                messages.success(request, "تخصیص اعتبار با سند تلگرام تطبیق و تسویه شد.")
            except (ValueError, TelegramAdsError) as exc:
                messages.error(request, str(exc))
        elif action == "link_ad":
            messages.error(request, "اتصال دستی شناسه بدون مستند تطبیق مجاز نیست.")
        else:
            messages.error(request, "اقدام نامعتبر است.")
            return redirect("operations:campaign_review", campaign_id=campaign.id)
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
    review_block = ""
    submit_block = ""
    try:
        review_payment_order(campaign)
    except ValueError as exc:
        review_block = str(exc)
    try:
        require_submission_order(campaign)
        from apps.operations.review import require_recorded_approval
        require_recorded_approval(campaign)
        if not settings.TELEGRAM_ADS_WRITE_ENABLED or not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
            raise ValueError("ارسال زنده در تنظیمات غیرفعال است.")
        if policy_run.blocked:
            raise ValueError("پیش‌شرط‌های سیاست یا مجوز اپراتور برقرار نیست.")
    except ValueError as exc:
        submit_block = str(exc)

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
            "review_block": review_block,
            "submit_block": submit_block,
            "allocation_pending": bool(order and order.status == AdvertisingOrder.Status.SUBMITTING),
        },
    )


@login_required
@staff_ops_required
def exchange_rates(request):
    from django.utils import timezone as tz

    from apps.finance.models import GramRateMarkupRule
    from apps.finance.services.gram_markup import (
        active_gram_markup_percent,
        apply_gram_markup_amount,
    )
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
    if request.method == "POST" and action == "save_markup":
        try:
            percent = int(request.POST.get("markup_percent", "0"))
        except ValueError:
            percent = -1
        if not 0 <= percent <= 100:
            messages.error(request, "درصد افزایش نرخ باید بین ۰ تا ۱۰۰ باشد.")
            return redirect("operations:exchange_rates")
        GramRateMarkupRule.objects.filter(is_active=True).update(is_active=False)
        GramRateMarkupRule.objects.create(percent=percent, is_active=True)
        AuditLog.objects.create(
            actor=request.user,
            action="exchange_rate.markup",
            entity_type="GramRateMarkupRule",
            new_state={"percent": percent},
        )
        messages.success(request, "درصد افزایش نرخ مشتری ذخیره شد.")
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
    markup_percent = active_gram_markup_percent()
    customer_ask = None
    if live and live.best_ask_irr is not None:
        customer_ask = apply_gram_markup_amount(live.best_ask_irr, percent=markup_percent)
    return render(
        request,
        "operations/exchange_rates.html",
        {
            "rates": rates,
            "live_rate": live,
            "fee_percent": settings.PLATFORM_SERVICE_FEE_PERCENT,
            "buffer_percent": settings.TON_PRICING_RISK_BUFFER_PERCENT,
            "markup_percent": markup_percent,
            "customer_ask_irr": customer_ask,
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
            "capability_count": capabilities.count(),
            "supported_count": capabilities.filter(state=APICapability.State.SUPPORTED).count(),
            "blocked_count": capabilities.filter(state__in=[APICapability.State.UNSUPPORTED, APICapability.State.PERMISSION_DENIED]).count(),
        },
    )


@login_required
@staff_ops_required
def audit_logs(request):
    from django.core.paginator import Paginator
    from django.db.models import Q

    query = request.GET.get("q", "").strip()[:100]
    entity = request.GET.get("entity", "").strip()
    entity_choices = [
        ("campaign", "کمپین"),
        ("refund", "بازپرداخت"),
        ("ExchangeRate", "نرخ گرام"),
        ("RelatedAccountRequest", "حساب مرتبط"),
    ]
    allowed = {value for value, _ in entity_choices}
    if entity not in allowed:
        entity = ""
    logs = AuditLog.objects.select_related("actor").order_by("-created_at", "-id")
    if query:
        logs = logs.filter(Q(actor__username__icontains=query)
                           | Q(action__icontains=query) | Q(entity_type__icontains=query))
    if entity:
        logs = logs.filter(entity_type=entity)
    page_obj = Paginator(logs, 30).get_page(request.GET.get("page"))
    return render(request, "operations/audit_logs.html", {
        "logs": page_obj.object_list, "page_obj": page_obj,
        "query": query, "entity": entity, "entity_choices": entity_choices,
    })


@login_required
@staff_ops_required
def refunds_ops(request):
    from django.core.paginator import Paginator
    from django.db.models import Q

    refunds = RefundRequest.objects.select_related("customer", "customer__user", "order").order_by("-created_at", "-id")
    status = request.GET.get("status", "")
    if status not in RefundRequest.Status.values:
        status = ""
    query = request.GET.get("q", "").strip()[:100]
    if status:
        refunds = refunds.filter(status=status)
    if query:
        refunds = refunds.filter(
            Q(customer__display_name__icontains=query)
            | Q(customer__company_name__icontains=query)
            | Q(customer__user__username__icontains=query)
            | Q(reason__icontains=query)
        )
    page_obj = Paginator(refunds, 25).get_page(request.GET.get("page"))
    refunds = page_obj.object_list

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
                mark_refund_in_review(refund, actor=request.user)
                messages.info(request, "در حال بررسی علامت‌گذاری شد.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("operations:refunds")

    return render(
        request,
        "operations/refunds.html",
        {"refunds": refunds, "filter_status": status,
         "query": query, "page_obj": page_obj},
    )
