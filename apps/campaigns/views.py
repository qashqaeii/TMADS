import copy
import csv
import json
import uuid
from decimal import Decimal, ROUND_DOWN

from django.contrib import messages
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, FileResponse, Http404
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone

from apps.accounts.permissions import customer_required
from apps.core.models import AuditLog
from apps.finance.models import AdvertisingOrder, PriceQuote
from apps.finance.invoice import issue_invoice_for_order
from apps.finance.services import calculate_quote_totals, ensure_wallet, reserve_for_order
from apps.finance.exceptions import PricingError
from apps.finance.services.ton_equiv import resolve_ton_display_rate
from apps.notifications.services import notify_customer

from .analytics import (
    aggregate_campaign_metrics,
    budget_delivery_context,
    campaign_chart_payload,
    chart_has_signal,
    campaign_lifecycle,
    funnel_from_metrics,
    portfolio_timeseries,
    targeting_display_rows,
)
from .metrics import (
    aggregate_portfolio_kpis,
    build_campaign_list_rows,
    optimize_campaign_list_queryset,
    sort_campaign_rows,
)
from .performance_insights import (
    build_portfolio_performance_insights,
    insight_badges_for_campaign,
)
from .creative_templates import CREATIVE_TEMPLATES
from .deletion import can_delete_draft_campaign, delete_draft_campaign
from .models import AdCreative, Campaign, CampaignStatisticsSnapshot, CampaignTargeting, CampaignStatusHistory, TelegramAdvertisement
from .ownership import get_customer_campaign
from .catalog import (
    get_countries,
    get_languages,
    get_topics,
    resolve_bot,
    resolve_channel,
    search_locations,
)
from .schedule_utils import IRAN_SCHEDULE_TIMEZONE_SEC, WEEKDAY_LABELS_FA, schedule_summary_fa
from .studio import (
    STUDIO_STEPS,
    apply_studio_step,
    ensure_studio_step,
    migrate_campaign_to_studio,
    studio_payload_from_post,
    validate_studio_step,
)
from .wizard import validate_step


@login_required
@customer_required
def campaign_list(request):
    customer = request.user.customer_profile
    base_qs = Campaign.objects.filter(customer=customer)
    has_any_campaigns = base_qs.exists()
    campaigns = optimize_campaign_list_queryset(base_qs)
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    placement = request.GET.get("placement", "").strip()
    filter_active = bool(q or status or placement)
    if q:
        campaigns = campaigns.filter(Q(name__icontains=q) | Q(destination__icontains=q))
    if status:
        campaigns = campaigns.filter(status=status)
    if placement:
        campaigns = campaigns.filter(placement=placement)

    sort = request.GET.get("sort", "-created_at")
    metric_sort_keys = {"views", "-views", "clicks", "-clicks", "ctr", "-ctr", "spent", "-spent"}
    if sort not in metric_sort_keys:
        if sort.lstrip("-") in {"created_at", "name", "status", "budget_irr"}:
            campaigns = campaigns.order_by(sort)

    rows = build_campaign_list_rows(campaigns)
    if sort in metric_sort_keys:
        rows = sort_campaign_rows(rows, sort)

    kpis = aggregate_portfolio_kpis(rows)
    performance_insights = build_portfolio_performance_insights(rows)
    portfolio_chart = portfolio_timeseries(request.user.customer_profile, days=30,
        campaign_ids=[row.campaign.pk for row in rows])
    paginator = Paginator(rows, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "campaigns/list.html",
        {
            "page_obj": page_obj,
            "campaign_rows": page_obj.object_list,
            "kpis": kpis,
            "performance_insights": performance_insights,
            "portfolio_chart_json": json.dumps(portfolio_chart, ensure_ascii=False),
            "has_portfolio_chart": bool(portfolio_chart.get("dates")),
            "sort": sort,
            "placement_choices": Campaign.Placement.choices,
            "status_choices": Campaign.Status.choices,
            "has_any_campaigns": has_any_campaigns,
            "filter_active": filter_active,
        },
    )


@login_required
@customer_required
@require_POST
def campaign_refresh_stats(request):
    """Read-only sync of linked Telegram ads + statistics for current customer."""
    from apps.telegram_ads.exceptions import TelegramAdsError
    from apps.telegram_ads.services.sync import (
        stats_sync_days,
        sync_ad_statistics_for,
    )

    customer = request.user.customer_profile
    campaign_id = (request.POST.get("campaign_id") or "").strip()
    campaign = get_customer_campaign(customer, campaign_id) if campaign_id else None
    if campaign:
        ads = TelegramAdvertisement.objects.filter(campaign=campaign).exclude(remote_ad_id="")
    else:
        ads = TelegramAdvertisement.objects.filter(campaign__customer=customer).exclude(remote_ad_id="")
    if not ads.exists():
        messages.info(request, "تبلیغ متصلی برای بروزرسانی نیست.")
        if campaign:
            return redirect("campaigns:detail", campaign_id=campaign.id)
        return redirect("campaigns:list")

    # A customer may only refresh their own linked ads, not the central account.
    if not cache.add(f"campaign-refresh:{customer.pk}", True, timeout=60):
        messages.info(request, "درخواست بروزرسانی اخیر ثبت شده است؛ لطفاً یک دقیقه صبر کنید.")
        if campaign:
            return redirect("campaigns:detail", campaign_id=campaign.id)
        return redirect("campaigns:list")

    refreshed = 0
    failed = 0
    from apps.telegram_ads.services.sync import sync_advertisement_detail

    for ad in ads.select_related("campaign"):
        try:
            sync_advertisement_detail(ad)
            sync_ad_statistics_for(ad, days=stats_sync_days(ad, ad.campaign))
            refreshed += 1
        except Exception:
            failed += 1

    if refreshed:
        messages.success(request, f"آمار {refreshed} تبلیغ بروزرسانی شد.")
    if failed:
        messages.warning(request, f"{failed} تبلیغ بدون آمار جدید (API یا محدودیت).")
    if campaign:
        return redirect("campaigns:detail", campaign_id=campaign.id)
    return redirect("campaigns:list")


@login_required
@customer_required
def campaign_detail(request, campaign_id):
    campaign = get_customer_campaign(
        request.user.customer_profile,
        campaign_id,
    )
    metrics = aggregate_campaign_metrics(campaign)
    from apps.telegram_ads.targeting.normalize import safe_destination_link
    destination_link = safe_destination_link(campaign.destination)
    chart = campaign_chart_payload(campaign, limit=None)
    order = AdvertisingOrder.objects.filter(campaign_id=campaign.id).first()
    creative = campaign.creatives.first()
    targeting = getattr(campaign, "targeting", None)
    history = campaign.status_history.all()[:30]
    remote_ads = campaign.remote_ads.all()
    last_sync = (
        campaign.remote_ads.order_by("-updated_at").values_list("updated_at", flat=True).first()
    )

    has_chart = bool(chart.get("dates"))
    order_exchange_rate_id = order.exchange_rate_id if order else None
    ton_irr_per_ton, _ = resolve_ton_display_rate(exchange_rate_id=order_exchange_rate_id)
    portfolio_rows = build_campaign_list_rows(
        optimize_campaign_list_queryset(
            Campaign.objects.filter(customer=request.user.customer_profile),
        ),
    )
    performance_insights = build_portfolio_performance_insights(portfolio_rows)
    performance_badges = insight_badges_for_campaign(performance_insights, campaign.id)
    return render(
        request,
        "campaigns/detail.html",
        {
            "campaign": campaign,
            "metrics": metrics,
            "can_edit_campaign": _campaign_editable(campaign),
            "destination_link": destination_link,
            "performance_badges": performance_badges,
            "has_chart": has_chart,
            "chart_has_signal": chart_has_signal(chart),
            "has_spend_chart": any(v is not None for v in chart.get("spent", [])),
            "chart_json": json.dumps(chart, ensure_ascii=False),
            "funnel_json": json.dumps(funnel_from_metrics(metrics), ensure_ascii=False),
            "budget": budget_delivery_context(campaign, metrics),
            "lifecycle_steps": campaign_lifecycle(campaign),
            "targeting_rows": targeting_display_rows(targeting),
            "order": order,
            "creative": creative,
            "targeting": targeting,
            "history": history,
            "remote_ads": remote_ads,
            "last_sync": last_sync,
            "can_delete_draft": can_delete_draft_campaign(campaign)[0],
            "order_exchange_rate_id": order_exchange_rate_id,
            "ton_irr_per_ton": int(ton_irr_per_ton) if ton_irr_per_ton else 0,
        },
    )


@login_required
@customer_required
@require_POST
def campaign_delete(request, campaign_id):
    campaign = get_customer_campaign(request.user.customer_profile, campaign_id)
    ok, reason = can_delete_draft_campaign(campaign)
    if not ok:
        messages.error(request, reason)
        return redirect("campaigns:detail", campaign_id=campaign.id)
    name = campaign.name or "پیش‌نویس"
    try:
        delete_draft_campaign(campaign)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("campaigns:list")
    AuditLog.objects.create(
        actor=request.user,
        action="campaign.deleted",
        entity_type="campaign",
        entity_id=campaign_id,
        new_state={"name": name, "status": Campaign.Status.DRAFT},
    )
    messages.success(request, f"پیش‌نویس «{name}» حذف شد.")
    return redirect("campaigns:list")


@login_required
@customer_required
@require_POST
@transaction.atomic
def campaign_duplicate(request, campaign_id):
    original = get_customer_campaign(request.user.customer_profile, campaign_id)
    clone = Campaign.objects.create(
        customer=original.customer,
        project=original.project,
        name=f"{(original.name or 'کمپین')[:194]} (کپی)",
        status=Campaign.Status.DRAFT,
        objective=original.objective,
        destination=original.destination,
        placement=original.placement,
        target_type=original.target_type,
        wizard_version=2,
        wizard_step=1,
        wizard_data={"studio_mode": (original.wizard_data or {}).get("studio_mode", "simple")},
        # New drafts require independent policy acceptance and eligibility checks.
        ad_settings={key: copy.deepcopy(value) for key, value in (original.ad_settings or {}).items()
                     if key in {"impression_frequency", "show_userpic", "additional_info"}},
        budget_irr=original.budget_irr,
        daily_cap_irr=original.daily_cap_irr,
        cpm_bid=original.cpm_bid,
    )
    if hasattr(original, "targeting") and original.targeting:
        config = copy.deepcopy(original.targeting.config or {})
        config.pop("bot_peer_checks", None)
        # Imported API targeting is not necessarily a valid editable studio payload.
        config.pop("api_target", None)
        config.pop("synced_at", None)
        config.pop("source", None)
        if config:
            CampaignTargeting.objects.create(campaign=clone, config=config)
    for cr in original.creatives.all():
        AdCreative.objects.create(
            campaign=clone,
            title=cr.title,
            ad_text=cr.ad_text,
            cta_label=cr.cta_label,
        )
    messages.success(request, "کمپین به‌صورت پیش‌نویس کپی شد.")
    return redirect("campaigns:wizard", campaign_id=clone.id)


@login_required
@customer_required
@transaction.atomic
def campaign_wizard(request, campaign_id=None):
    customer = request.user.customer_profile

    if campaign_id is None:
        campaign = Campaign.objects.create(
            customer=customer,
            name="کمپین جدید",
            wizard_version=2,
        )
        return redirect("campaigns:wizard", campaign_id=campaign.id)

    campaign = get_customer_campaign(customer, campaign_id)
    if request.method == "POST":
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    if not _campaign_editable(campaign):
        messages.info(request, "این کمپین ثبت شده و قابل ویرایش در استودیو نیست. برای ساخت نسخه جدید از کپی کمپین استفاده کنید.")
        return redirect("campaigns:detail", campaign_id=campaign.id)
    migrate_campaign_to_studio(campaign)
    step = ensure_studio_step(campaign)
    campaign.wizard_step = step
    max_step = len(STUDIO_STEPS)

    if request.method == "POST":
        action = request.POST.get("action", "next")
        if not _draft_revision_matches(campaign, request.POST):
            messages.error(request, "نسخه یا مرحله پیش‌نویس تغییر کرده است؛ صفحه جدید را بررسی کنید.")
            return redirect("campaigns:wizard", campaign_id=campaign.id)
        if action == "refresh_quote" and step == max_step:
            try:
                _create_quote(campaign)
                messages.success(request, "پیش‌فاکتور جدید آماده است. مبلغ را بررسی و سپس پرداخت کنید.")
            except PricingError as exc:
                messages.error(request, str(exc))
            return redirect("campaigns:wizard", campaign_id=campaign.id)
        strict_next = action in {"next", "pay"}
        try:
            errors = validate_studio_step(campaign, step, request.POST, strict=strict_next)
        except (TypeError, ValueError, OverflowError):
            errors = ["فرمت اطلاعات واردشده معتبر نیست."]
        upload = request.FILES.get("creative_media")
        if upload:
            from apps.campaigns.media_validation import validate_creative_media
            if step != 3 or campaign.target_type not in {"channels", "users"}:
                errors.append("این نوع تبلیغ از فایل رسانه پشتیبانی نمی‌کند.")
            elif request.POST.get("remove_creative_media") == "1":
                errors.append("حذف فایل و بارگذاری فایل جدید را هم‌زمان انتخاب نکنید.")
            else:
                errors.extend(validate_creative_media(upload))
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            apply_studio_step(campaign, step, request.POST, files=request.FILES)
            campaign.wizard_data = {**campaign.wizard_data, **studio_payload_from_post(request.POST)}
            campaign.draft_revision += 1
            campaign.draft_saved_at = timezone.now()
            campaign.save()

            if action == "back" and step > 1:
                campaign.wizard_step = step - 1
                campaign.save(update_fields=["wizard_step", "updated_at"])
            elif action == "save_draft":
                messages.success(request, "پیش‌نویس ذخیره شد.")
            elif step == max_step and action == "pay":
                pay_errors = validate_studio_step(campaign, step, request.POST, strict=True)
                if pay_errors:
                    for e in pay_errors:
                        messages.error(request, e)
                else:
                    from apps.policies.constants import FindingSeverity
                    from apps.policies.services.preflight import CampaignPolicyPreflight

                    policy = CampaignPolicyPreflight(campaign).run(
                        strict=True,
                        context="wizard_pay",
                        check_operator=False,
                    )
                    if policy.blocked:
                        for finding in policy.findings:
                            if finding.severity == FindingSeverity.BLOCKED:
                                messages.error(request, finding.message_fa)
                    else:
                        if request.POST.get("terms_accepted") != "1":
                            messages.error(request, "پذیرش قوانین برای پرداخت الزامی است.")
                            return redirect("campaigns:wizard", campaign_id=campaign.id)
                        if not _handle_payment_submission(request, campaign):
                            return redirect("campaigns:wizard", campaign_id=campaign.id)
                        acceptance = (
                            "مشتری تأیید می‌کند حق تبلیغ مقصد را دارد، محتوا دقیق است، "
                            "بررسی نهایی با تلگرام است و تأیید TMADS تضمین نمایش نیست."
                        )
                        campaign.refresh_from_db()
                        CampaignPolicyPreflight.record_acceptance(
                            campaign,
                            request=request,
                            acceptance_text=acceptance,
                        )
                        CampaignPolicyPreflight(campaign).run(
                            strict=True,
                            context="post_payment",
                            check_operator=False,
                        )
                        return redirect("campaigns:detail", campaign_id=campaign.id)
            elif step < max_step and action == "next":
                campaign.wizard_step = step + 1
                campaign.save(update_fields=["wizard_step", "updated_at"])
                if step == 4:
                    try:
                        _create_quote(campaign)
                    except PricingError as exc:
                        messages.error(request, str(exc))
            else:
                messages.info(request, "تغییرات ذخیره شد.")

            return redirect("campaigns:wizard", campaign_id=campaign.id)

    quote = None
    order = AdvertisingOrder.objects.filter(campaign_id=campaign.id, customer=customer).first()
    if order and hasattr(order, "quote"):
        quote = order.quote
    quote_ready = bool(order and _quote_valid(campaign, order, quote))
    quote_totals = (
        quote.payload if step == max_step and quote_ready
        else calculate_quote_totals(campaign.budget_irr) if step == 4 and campaign.budget_irr else None
    )

    creative = campaign.creatives.first()
    wallet = ensure_wallet(customer)
    ton_rate_display = None
    try:
        from apps.finance.services.ton_exchange_rate import get_cached_snapshot

        snap = get_cached_snapshot(allow_stale_display=True)
        if snap:
            ton_rate_display = snap
    except Exception:
        pass
    from apps.telegram_ads.services.ad_write import dry_run_create_ad
    from apps.telegram_ads.targeting.compatibility import placement_choices_for_target
    from apps.telegram_ads.targeting.validators import validate_studio_config

    targeting = getattr(campaign, "targeting", None)
    validation_preview = validate_studio_config(
        target_type=campaign.target_type,
        placement=campaign.placement,
        config=targeting.config if targeting else {},
        promote_url=campaign.destination,
        ad_text=creative.ad_text if creative else "",
        title=campaign.name,
        ad_settings=campaign.ad_settings or {},
        strict=False,
    )
    dry_run = None
    if campaign.budget_irr and campaign.target_type:
        try:
            dry_run = dry_run_create_ad(campaign)
        except Exception:
            dry_run = None

    from apps.policies.services.engine import evaluate_campaign

    policy_run = evaluate_campaign(
        campaign,
        strict=False,
        include_budget_info=(step == 4),
        check_operator=False,
    )

    ad_settings = campaign.ad_settings or {}
    schedule_obj = ad_settings.get("schedule") or {}
    studio_mode = (campaign.wizard_data or {}).get("studio_mode") or "simple"
    if studio_mode not in ("simple", "professional"):
        studio_mode = "simple"

    ctx = {
        "campaign": campaign,
        "step": step,
        "steps": STUDIO_STEPS,
        "target_placement_choices": placement_choices_for_target(campaign.target_type or "channels"),
        "studio_feedback": validation_preview,
        "dry_run_preview": dry_run,
        "quote": quote,
        "quote_totals": quote_totals,
        "quote_ready": quote_ready,
        "creative_templates": CREATIVE_TEMPLATES,
        "creative": creative,
        "wallet": wallet,
        "ton_rate_display": ton_rate_display,
        "target_type_choices": Campaign.TargetType.choices,
        "impression_frequency_choices": [1, 2, 3, 4],
        "search_queries_json": json.dumps(
            (getattr(getattr(campaign, "targeting", None), "config", {}) or {}).get("search_queries") or [],
            ensure_ascii=False,
        ),
        "bot_eligibility_json": json.dumps(
            (getattr(getattr(campaign, "targeting", None), "config", {}) or {}).get("bot_peer_checks") or {},
            ensure_ascii=False,
        ),
        "dry_run_json": json.dumps(dry_run.get("payload") if isinstance(dry_run, dict) and dry_run.get("payload") else {}, ensure_ascii=False),
        "policy_run": policy_run,
        "studio_mode": studio_mode,
        "catalog_countries_json": json.dumps(get_countries() if step == 2 and campaign.target_type == "users" else [], ensure_ascii=False),
        "catalog_languages_json": json.dumps(get_languages() if step == 2 and campaign.target_type in {"channels", "users"} else [], ensure_ascii=False),
        "catalog_topics_json": json.dumps(get_topics() if step == 2 and campaign.target_type in {"channels", "users"} else [], ensure_ascii=False),
        "schedule_json": json.dumps(schedule_obj, ensure_ascii=False),
        "schedule_enabled": bool(schedule_obj.get("week_hours_mask")),
        "schedule_timezone": schedule_obj.get("timezone") or IRAN_SCHEDULE_TIMEZONE_SEC,
        "schedule_summary": schedule_summary_fa(schedule_obj if schedule_obj else None),
        "schedule_hours": list(range(24)),
        "schedule_weekdays": [{"index": i, "label": label} for i, label in enumerate(WEEKDAY_LABELS_FA)],
        "policy_preview_url": reverse("campaigns:policy_preview", kwargs={"campaign_id": campaign.id}),
    }
    return render(request, "campaigns/wizard.html", ctx)


@login_required
@customer_required
@require_POST
@transaction.atomic
def campaign_autosave(request, campaign_id):
    customer = request.user.customer_profile
    campaign = get_customer_campaign(customer, campaign_id)
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    if not _campaign_editable(campaign):
        return JsonResponse({"ok": False, "message": "این کمپین دیگر قابل ویرایش نیست."}, status=409)
    migrate_campaign_to_studio(campaign)
    if not _draft_revision_matches(campaign, request.POST):
        return JsonResponse({"ok": False, "conflict": True, "server_revision": campaign.draft_revision,
            "message": "نسخه یا مرحله پیش‌نویس تغییر کرده است. صفحه را تازه کنید."}, status=409)
    step = ensure_studio_step(campaign)
    try:
        errors = validate_studio_step(campaign, step, request.POST, strict=False)
    except (TypeError, ValueError, OverflowError):
        errors = ["فرمت داده‌های پیش‌نویس معتبر نیست."]
    if errors:
        return JsonResponse({"ok": False, "message": "؛ ".join(errors)}, status=400)
    try:
        with transaction.atomic():
            data = request.POST.copy()
            data.pop("remove_creative_media", None)
            apply_studio_step(campaign, step, data)
    except (ValueError, TypeError, OverflowError):
        return JsonResponse({"ok": False, "message": "اطلاعات پیش‌نویس معتبر نیست."}, status=400)
    campaign.wizard_data = {**campaign.wizard_data, **studio_payload_from_post(request.POST)}
    campaign.draft_revision += 1
    campaign.draft_saved_at = timezone.now()
    campaign.save()
    return JsonResponse(
        {
            "ok": True,
            "revision": campaign.draft_revision,
            "saved_at": campaign.draft_saved_at.isoformat(),
        }
    )


def _apply_creative_template(campaign: Campaign, template_id: str) -> None:
    data = next((t for t in CREATIVE_TEMPLATES if t["id"] == template_id), None)
    if not data:
        return
    creative, _ = AdCreative.objects.get_or_create(campaign=campaign)
    creative.title = data["title"]
    creative.ad_text = data["text"]
    creative.cta_label = data["cta_label"]
    creative.save()


def _apply_step(campaign: Campaign, step: int, data) -> None:
    if step == 1:
        campaign.objective = data.get("objective", "")
    elif step == 2:
        campaign.destination = data.get("destination", "").strip()
    elif step == 3:
        campaign.placement = data.get("placement", "")
    elif step == 4:
        CampaignTargeting.objects.update_or_create(
            campaign=campaign,
            defaults={"config": _targeting_from_post(data)},
        )
    elif step == 5:
        creative, _ = AdCreative.objects.get_or_create(campaign=campaign)
        creative.ad_text = data.get("ad_text", "").strip()
        creative.title = data.get("creative_title", "").strip() or campaign.name
        creative.cta_label = data.get("cta_label", "").strip()
        creative.save()
    elif step == 6:
        try:
            budget_toman = int(data.get("budget_toman") or 0)
        except ValueError:
            budget_toman = 0
        campaign.budget_irr = budget_toman * 10_000
        campaign.name = data.get("campaign_name", "").strip() or campaign.name
        try:
            daily_toman = int(data.get("daily_cap_toman") or 0)
        except ValueError:
            daily_toman = 0
        campaign.daily_cap_irr = daily_toman * 10_000 if daily_toman else 0
        cpm_raw = (data.get("cpm_bid") or "").strip()
        if cpm_raw:
            from decimal import Decimal, InvalidOperation

            try:
                campaign.cpm_bid = Decimal(cpm_raw)
            except InvalidOperation:
                pass
        start_raw = (data.get("schedule_start") or "").strip()
        end_raw = (data.get("schedule_end") or "").strip()
        if start_raw:
            campaign.schedule_start = timezone.datetime.fromisoformat(start_raw)
            if timezone.is_naive(campaign.schedule_start):
                campaign.schedule_start = timezone.make_aware(campaign.schedule_start)
        if end_raw:
            campaign.schedule_end = timezone.datetime.fromisoformat(end_raw)
            if timezone.is_naive(campaign.schedule_end):
                campaign.schedule_end = timezone.make_aware(campaign.schedule_end)
        campaign.save(
            update_fields=[
                "budget_irr",
                "name",
                "daily_cap_irr",
                "cpm_bid",
                "schedule_start",
                "schedule_end",
                "updated_at",
            ]
        )


def _targeting_from_post(data) -> dict:
    lang_list: list[str] = []
    if hasattr(data, "getlist"):
        lang_list = list(data.getlist("languages"))
    extra = (data.get("languages_extra") or "").strip()
    if extra:
        lang_list.extend(part.strip() for part in extra.split(",") if part.strip())
    elif not lang_list and data.get("languages"):
        lang_list = [str(data.get("languages"))]
    return {
        "countries": data.getlist("countries") if hasattr(data, "getlist") else [],
        "languages": ",".join(dict.fromkeys(lang_list)),
        "topics": data.get("topics", ""),
        "advanced": data.get("advanced_targeting", ""),
    }


def _draft_revision_matches(campaign, data):
    try:
        return int(data.get("draft_revision", "-1")) == campaign.draft_revision and int(data.get("studio_step", "-1")) == ensure_studio_step(campaign)
    except (ValueError, TypeError):
        return False


def _campaign_editable(campaign):
    if campaign.status not in {Campaign.Status.DRAFT, Campaign.Status.AWAITING_PAYMENT}:
        return False
    if campaign.remote_ads.exclude(remote_ad_id="").exists():
        return False
    return not AdvertisingOrder.objects.filter(
        campaign_id=campaign.id,
    ).exclude(status__in=[AdvertisingOrder.Status.DRAFT, AdvertisingOrder.Status.AWAITING_PAYMENT]).exists()


def _quote_valid(campaign, order, quote):
    if not quote or order.status != AdvertisingOrder.Status.AWAITING_PAYMENT:
        return False
    payload = quote.payload or {}
    return bool(
        order.total_irr > 0 and order.ton_allocation > 0
        and order.quote_expires_at and order.quote_expires_at > timezone.now()
        and quote.expires_at > timezone.now()
        and quote.locked_total_irr == order.total_irr
        and payload.get("quote_status") == "locked"
        and payload.get("quote_nonce")
        and payload.get("buffer_disposition") == "return_after_confirmed_allocation"
        and payload.get("requested_budget_irr") == campaign.budget_irr
        and payload.get("requested_daily_cap_irr") == campaign.daily_cap_irr
        and str(order.ton_allocation) == str(Decimal(str(payload.get("ton_allocation", "0"))).quantize(Decimal("0.000000001")))
    )


@transaction.atomic
def _create_quote(campaign: Campaign) -> None:
    from datetime import datetime
    from apps.finance.services.campaign_pricing import build_campaign_quote

    if not _campaign_editable(campaign):
        raise PricingError("سفارش ثبت‌شده قابل بازقیمت‌گذاری نیست.")
    totals = build_campaign_quote(campaign.budget_irr)
    if totals.get("quote_status") != "locked":
        raise PricingError("نرخ معتبر برای ساخت پیش‌فاکتور در دسترس نیست.")
    daily_ton = (Decimal(campaign.daily_cap_irr) / Decimal(totals["effective_rate_irr"])).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN,
    )
    if (campaign.daily_cap_irr < 0 or campaign.daily_cap_irr > campaign.budget_irr
            or daily_ton > Decimal(totals["ton_allocation"])
            or (campaign.daily_cap_irr and daily_ton <= 0)):
        raise PricingError("سقف روزانه باید معتبر و حداکثر برابر بودجه تبلیغ باشد.")
    totals = {
        **totals,
        "daily_limit_ton": str(daily_ton),
        "quote_nonce": uuid.uuid4().hex,
        "buffer_disposition": "return_after_confirmed_allocation",
        "requested_budget_irr": campaign.budget_irr,
        "requested_daily_cap_irr": campaign.daily_cap_irr,
    }
    quote_expires = datetime.fromisoformat(str(totals["expires_at"]).replace("Z", "+00:00"))
    if timezone.is_naive(quote_expires):
        quote_expires = timezone.make_aware(quote_expires)
    ton = Decimal(str(totals["ton_allocation"]))
    if ton <= 0 or totals["total_irr"] <= 0:
        raise PricingError("مبلغ پیش‌فاکتور معتبر نیست.")

    rate_id = totals.get("exchange_rate_id")
    order, _ = AdvertisingOrder.objects.update_or_create(
        campaign_id=campaign.id,
        customer=campaign.customer,
        defaults={
            "status": AdvertisingOrder.Status.AWAITING_PAYMENT,
            "advertising_budget_irr": totals["advertising_budget_irr"],
            "service_fee_irr": totals["service_fee_irr"],
            "total_irr": totals["total_irr"],
            "ton_allocation": ton,
            "quote_expires_at": quote_expires,
            "exchange_rate_id": rate_id if rate_id else None,
        },
    )
    PriceQuote.objects.update_or_create(
        order=order,
        defaults={
            "payload": totals,
            "expires_at": quote_expires,
            "locked_total_irr": totals["total_irr"],
        },
    )
    previous = campaign.status
    campaign.status = Campaign.Status.AWAITING_PAYMENT
    campaign.save(update_fields=["status", "updated_at"])
    CampaignStatusHistory.objects.create(
        campaign=campaign,
        from_status=previous,
        to_status=campaign.status,
        note="ایجاد پیش‌فاکتور",
    )
    notify_customer(
        campaign.customer,
        "پیش‌فاکتور آماده است",
        f"کمپین «{campaign.name}» آماده پرداخت است.",
        related_campaign_id=campaign.id,
    )


@transaction.atomic
def _handle_payment_submission(request, campaign: Campaign) -> bool:
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    if not _campaign_editable(campaign):
        messages.error(request, "این سفارش قبلاً ثبت شده یا در وضعیت قابل پرداخت نیست.")
        return False
    order = AdvertisingOrder.objects.select_for_update().filter(
        campaign_id=campaign.id, customer=campaign.customer,
    ).first()
    quote = getattr(order, "quote", None) if order else None
    if not order or not _quote_valid(campaign, order, quote):
        messages.error(request, "پیش‌فاکتور معتبر نیست یا منقضی شده؛ ابتدا آن را به‌روزرسانی کنید.")
        return False
    if request.POST.get("quote_nonce") != quote.payload.get("quote_nonce"):
        messages.error(request, "مبلغ پیش‌فاکتور تغییر کرده؛ صفحه را تازه و دوباره بررسی کنید.")
        return False

    wallet = ensure_wallet(campaign.customer)
    try:
        reserve_for_order(
            wallet,
            order.total_irr,
            order.id,
            idempotency_key=f"order-reserve-{order.id}",
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return False

    order.status = AdvertisingOrder.Status.PAID
    order.save(update_fields=["status", "updated_at"])
    previous = campaign.status
    campaign.status = Campaign.Status.PENDING_REVIEW
    campaign.save(update_fields=["status", "updated_at"])
    CampaignStatusHistory.objects.create(
        campaign=campaign,
        from_status=previous,
        to_status=campaign.status,
        note="پرداخت از کیف پول — در صف بررسی",
    )
    AuditLog.objects.create(
        actor=request.user,
        action="campaign.paid",
        entity_type="campaign",
        entity_id=campaign.id,
        new_state={"order_id": str(order.id), "total_irr": order.total_irr},
    )
    issue_invoice_for_order(order, campaign.customer)
    notify_customer(
        campaign.customer,
        "پرداخت کمپین موفق",
        "سفارش شما ثبت شد و در انتظار بررسی عملیات است.",
        level="success",
        related_campaign_id=campaign.id,
    )
    messages.success(request, "پرداخت تأیید شد. سفارش در صف بررسی قرار گرفت.")
    return True


@login_required
@customer_required
@require_GET
def studio_catalog_countries(request):
    return JsonResponse({"ok": True, "items": get_countries()})


@login_required
@customer_required
@require_GET
def studio_catalog_languages(request):
    return JsonResponse({"ok": True, "items": get_languages()})


@login_required
@customer_required
@require_GET
def studio_catalog_topics(request):
    return JsonResponse({"ok": True, "items": get_topics()})


@login_required
@customer_required
@require_GET
def studio_catalog_locations(request):
    country = (request.GET.get("country") or "").strip().upper()
    q = (request.GET.get("q") or "").strip()
    from apps.telegram_ads.exceptions import TelegramAdsError
    if _catalog_rate_limited(request.user.pk, "locations"):
        return JsonResponse({"ok": False, "message": "چند لحظه صبر کنید."}, status=429)
    try:
        items = search_locations(country, q, limit=20, raise_on_unavailable=True)
    except TelegramAdsError as exc:
        return JsonResponse({"ok": False, "message": str(exc)}, status=503)
    return JsonResponse({"ok": True, "items": items})


_BOT_RESOLVE_LIMIT = 40
_BOT_RESOLVE_WINDOW = 60


def _catalog_rate_limited(user_id: int, kind: str) -> bool:
    key = f"tmads:rate:catalog:{kind}:{user_id}"
    cache.add(key, 0, _BOT_RESOLVE_WINDOW)
    try:
        return cache.incr(key) > _BOT_RESOLVE_LIMIT
    except ValueError:
        return True


def _bot_resolve_rate_limited(user_id: int) -> bool:
    return _catalog_rate_limited(user_id, "bot")


@login_required
@customer_required
@require_GET
def studio_catalog_resolve_bot(request):
    if _bot_resolve_rate_limited(request.user.pk):
        return JsonResponse(
            {
                "ok": False,
                "eligibility": "api_unavailable",
                "message_fa": "تعداد درخواست بررسی زیاد است؛ چند لحظه صبر کنید.",
                "hard_block": False,
                "verified": False,
            },
            status=429,
        )
    username = (request.GET.get("username") or request.GET.get("q") or "").strip()
    return JsonResponse(resolve_bot(username))


@login_required
@customer_required
@require_GET
def studio_catalog_resolve_channel(request):
    if _catalog_rate_limited(request.user.pk, "channel"):
        return JsonResponse({"ok": False, "pending": True, "error": "چند لحظه صبر کنید."}, status=429)
    username = (request.GET.get("username") or "")[:256]
    return JsonResponse(resolve_channel(username))


@login_required
@customer_required
@require_POST
@transaction.atomic
def campaign_policy_preview(request, campaign_id):
    customer = request.user.customer_profile
    campaign = get_customer_campaign(customer, campaign_id)
    campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
    if not _campaign_editable(campaign):
        return JsonResponse({"ok": False, "message": "کمپین ثبت شده و قابل تغییر نیست."}, status=409)
    if not _draft_revision_matches(campaign, request.POST):
        return JsonResponse({"ok": False, "message": "نسخه پیش‌نویس تغییر کرده است."}, status=409)
    rate_key = f"tmads:policy_preview:{request.user.pk}"
    if cache.get(rate_key):
        return JsonResponse({"ok": False, "message": "لطفاً چند ثانیه صبر کنید."}, status=429)
    cache.set(rate_key, 1, 3)
    step = ensure_studio_step(campaign)
    try:
        errors = validate_studio_step(campaign, step, request.POST, strict=False)
        if errors:
            transaction.set_rollback(True)
            return JsonResponse({"ok": False, "message": "؛ ".join(errors)}, status=400)
        apply_studio_step(campaign, step, request.POST)  # never write media for a preview
    except (TypeError, ValueError, OverflowError):
        transaction.set_rollback(True)
        return JsonResponse({"ok": False, "message": "اطلاعات پیش‌نمایش نامعتبر است."}, status=400)
    from apps.policies.services.engine import evaluate_campaign

    run = evaluate_campaign(
        campaign,
        strict=False,
        check_operator=False,
        include_budget_info=(step >= 4),
    )
    findings = [
        {
            "severity": f.severity,
            "message_fa": f.message_fa,
            "field_key": f.field_key,
        }
        for f in run.findings
    ]
    transaction.set_rollback(True)  # policy preview must never persist campaign/creative changes
    return JsonResponse(
        {
            "ok": True,
            "counts": run.counts(),
            "findings": findings,
            "ready": not run.blocked and not run.needs_manual_review,
        }
    )


@login_required
@customer_required
def campaign_export_csv(request, campaign_id):
    campaign = get_customer_campaign(request.user.customer_profile, campaign_id)
    snapshots = (
        CampaignStatisticsSnapshot.objects.filter(advertisement__campaign=campaign)
        .order_by("snapshot_date")
        .values("snapshot_date", "impressions", "clicks", "actions", "spent_ton")
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="campaign-{campaign.id}.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(["date", "impressions", "clicks", "actions", "spent_ton"])
    for row in snapshots:
        writer.writerow(
            [
                row["snapshot_date"].isoformat(),
                row["impressions"],
                row["clicks"],
                row["actions"],
                row["spent_ton"],
            ]
        )
    return response


@login_required
@require_GET
def creative_media_download(request, campaign_id, creative_id):
    user = request.user
    if user.is_platform_manager:
        campaign = get_object_or_404(Campaign, pk=campaign_id)
    else:
        customer = getattr(user, "customer_profile", None)
        if not customer or customer.is_suspended:
            raise Http404
        campaign = get_customer_campaign(customer, campaign_id)
    creative = get_object_or_404(AdCreative, pk=creative_id, campaign=campaign)
    if not creative.media:
        raise Http404
    try:
        handle = creative.media.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404
    from pathlib import Path
    response = FileResponse(handle, as_attachment=True, filename=Path(creative.media.name).name,
                            content_type="application/octet-stream")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
