"""Explicit customer-initiated AI calls; no campaign changes or Telegram writes."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from apps.accounts.permissions import customer_required
from apps.ai.provider import AiError, available
from apps.ai.features import (
    analyze_campaign,
    creative_variants,
    optimize_campaign,
    plan_campaign,
)
from .ownership import get_customer_campaign
from .studio import ensure_studio_step

ERRORS = {
    "insufficient_data": ("برای تحلیل قابل اتکا، ابتدا آمار معتبر و تازه دریافت کنید.", 409),
    "disabled": ("دستیار هوشمند در حال حاضر فعال نیست.", 503),
    "missing_input": ("توضیح کوتاهی درباره محصول یا متن فعلی وارد کنید.", 400),
    "quota": ("سهمیه روزانه هوش مصنوعی به پایان رسیده است.", 429),
    "feature_quota": ("سهمیه روزانه این قابلیت به پایان رسیده است.", 429),
    "busy": ("درخواست دیگری در حال پردازش است؛ کمی بعد دوباره تلاش کنید.", 429),
    "rate_limited": ("سرویس هوش مصنوعی موقتاً محدود شده است؛ کمی بعد دوباره تلاش کنید.", 429),
    "provider_auth": ("اتصال سرویس هوش مصنوعی نیاز به بررسی تنظیمات دسترسی دارد.", 503),
    "no_safe_output": ("پیشنهاد مناسبی دریافت نشد؛ توضیح را دقیق‌تر کنید.", 422),
    "invalid_input": ("اطلاعات ورودی معتبر نیست.", 400),
    "invalid_output": ("پاسخ قابل استفاده نبود؛ اطلاعات شما بدون تغییر باقی ماند.", 502),
    "provider_unavailable": ("دستیار موقتاً در دسترس نیست؛ بدون آن ادامه دهید.", 503),
}


def fail(exc):
    message, status = ERRORS.get(str(exc), ERRORS["provider_unavailable"])
    return JsonResponse({"ok": False, "message": message}, status=status)


@never_cache
@login_required
@customer_required
@require_POST
def plan(request, campaign_id):
    campaign = get_customer_campaign(request.user.customer_profile, campaign_id)
    if not available():
        return fail(AiError("disabled"))
    from .views import _campaign_editable
    if not _campaign_editable(campaign) or ensure_studio_step(campaign) != 1:
        return JsonResponse(
            {"ok": False, "message": "برنامه‌ریزی هوشمند فقط در مرحله اول پیش‌نویس قابل استفاده است."},
            status=409,
        )
    try:
        result, cached = plan_campaign(
            campaign.customer,
            campaign,
            request.POST.get("brief", ""),
            audience=request.POST.get("audience", ""),
            goal=request.POST.get("goal", ""),
        )
    except AiError as exc:
        return fail(exc)
    return JsonResponse({"ok": True, "plan": result, "cached": cached})


@never_cache
@login_required
@customer_required
@require_POST
def creative(request, campaign_id):
    from .views import _campaign_editable
    campaign = get_customer_campaign(request.user.customer_profile, campaign_id)
    if not available():
        return fail(AiError("disabled"))
    if not _campaign_editable(campaign) or ensure_studio_step(campaign) != 3 or campaign.target_type not in {"channels", "users", "bots"}:
        return JsonResponse({"ok": False, "message": "پیشنهاد متن فقط در مرحله محتوای پیش‌نویس فعال است."}, status=409)
    try:
        result, cached = creative_variants(
            campaign.customer,
            campaign,
            request.POST.get("brief", ""),
            request.POST.get("current", ""),
        )
    except AiError as exc:
        return fail(exc)
    return JsonResponse({"ok": True, **result, "cached": cached})


@never_cache
@login_required
@customer_required
@require_POST
def analysis(request, campaign_id):
    campaign = get_customer_campaign(request.user.customer_profile, campaign_id)
    if not available():
        return fail(AiError("disabled"))
    try:
        result, cached = analyze_campaign(campaign.customer, campaign)
    except AiError as exc:
        return fail(exc)
    return JsonResponse({"ok": True, **result, "cached": cached})


@never_cache
@login_required
@customer_required
@require_POST
def optimization(request, campaign_id):
    campaign = get_customer_campaign(request.user.customer_profile, campaign_id)
    if not available():
        return fail(AiError("disabled"))
    try:
        result, cached = optimize_campaign(campaign.customer, campaign)
    except AiError as exc:
        return fail(exc)
    return JsonResponse({"ok": True, **result, "cached": cached})
