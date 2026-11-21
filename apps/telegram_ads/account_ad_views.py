"""Read-only, individually authorized child-account ad inventory."""
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.shortcuts import render

from apps.accounts.permissions import customer_required
from apps.telegram_ads.services.customer_assets import owned_account, verified_client
from apps.telegram_ads.exceptions import TelegramAdsError


@login_required
@customer_required
@never_cache
@require_GET
def related_account_ads(request):
    row = owned_account(request.user)
    context = {"row": row, "items": [], "loaded": False, "next_offset": None}
    if not row:
        return render(request, "accounts/related_ads.html", context)
    if request.GET.get("load") != "1":
        return render(request, "accounts/related_ads.html", context)
    cursor = request.GET.get("offset") or None
    if cursor and (len(cursor) > 512 or any(ord(char) < 33 for char in cursor)):
        context["error"] = "شناسه صفحه‌بندی معتبر نیست."
        return render(request, "accounts/related_ads.html", context)
    try:
        client = verified_client(row)
        page = client.get_account_ads_page(
            account_id=None, offset=cursor, limit=40,
        )
        if not isinstance(page, dict) or not isinstance(page.get("ads"), list):
            raise ValueError("ساختار اطلاعات تبلیغات معتبر نیست.")
        raw = page["ads"]
        if any(not isinstance(item, dict) or type(item.get("ad_id")) is not int
               or item["ad_id"] <= 0 for item in raw):
            raise ValueError("شناسه‌های تبلیغ معتبر نیستند.")
        if len({item["ad_id"] for item in raw}) != len(raw):
            raise ValueError("پاسخ تبلیغات شامل شناسه تکراری است.")
        offset = page.get("next_offset")
        if offset is not None and (not isinstance(offset, str) or len(offset) > 512):
            raise ValueError("نشانه صفحه بعدی معتبر نیست.")
        if offset and not raw:
            raise ValueError("صفحه‌بندی ناقص از API برگشت.")
        context.update(
            items=raw, loaded=True, next_offset=offset,
            total_count=page.get("total_count") if type(page.get("total_count")) is int else None,
        )
    except (ValueError, TelegramAdsError):
        context["error"] = "دریافت تبلیغات حساب اختصاصی ممکن نشد. مالکیت و اتصال را بررسی کنید."
    return render(request, "accounts/related_ads.html", context)
