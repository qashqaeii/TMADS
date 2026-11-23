"""Read-only, individually authorized child-account ad inventory."""
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, render

from apps.accounts.permissions import customer_required
from apps.telegram_ads.services.customer_assets import owned_account, verified_client
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.models import TelegramAdsConnection
from apps.telegram_ads.services.account_connections import connection_client, default_connection


@login_required
@customer_required
@never_cache
@require_GET
def related_account_ads(request):
    profile = request.user.customer_profile
    selected_id = request.GET.get("connection_id")
    connection = (
        get_object_or_404(
            TelegramAdsConnection,
            pk=selected_id,
            customer=profile,
            status=TelegramAdsConnection.Status.CONNECTED,
        )
        if selected_id else default_connection(profile)
    )
    # Keep existing legacy related-account links functional when no connection exists.
    row = connection.related_account if connection and connection.related_account_id else (
        owned_account(request.user) if not connection else None
    )
    context = {
        "row": row, "connection": connection, "items": [],
        "loaded": False, "next_offset": None,
    }
    if not row and not connection:
        return render(request, "accounts/related_ads.html", context)
    if request.GET.get("load") != "1":
        return render(request, "accounts/related_ads.html", context)
    cursor = request.GET.get("offset") or None
    if cursor and (len(cursor) > 512 or any(ord(char) < 33 for char in cursor)):
        context["error"] = "شناسه صفحه‌بندی معتبر نیست."
        return render(request, "accounts/related_ads.html", context)
    try:
        if connection:
            client = connection_client(connection)
            if connection.is_customer_owned:
                page = client.get_ads_page(offset=cursor, limit=40)
            else:
                page = client.get_account_ads_page(
                    account_id=connection.remote_account_id, offset=cursor, limit=40,
                )
        else:
            client = verified_client(row)
            page = client.get_account_ads_page(
                account_id=row.remote_account_id, offset=cursor, limit=40,
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
