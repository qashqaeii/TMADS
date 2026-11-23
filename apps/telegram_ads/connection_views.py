"""Customer-owned and platform-managed Telegram Ads account workspace."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import customer_required
from apps.telegram_ads.models import TelegramAdsConnection
from apps.telegram_ads.services.account_connections import (
    connect_customer_owned_account,
    disconnect_customer_owned_account,
    refresh_connection,
    set_default_connection,
)


@login_required
@customer_required
@never_cache
@require_http_methods(["GET", "POST"])
def customer_telegram_connections(request):
    profile = request.user.customer_profile
    if request.method == "POST":
        action = str(request.POST.get("action") or "")
        try:
            if action == "connect":
                connect_customer_owned_account(request.user, request.POST.get("api_token", ""))
                messages.success(request, "حساب Telegram Ads متصل شد و هویت و موجودی آن بررسی شد.")
            elif action == "disconnect":
                disconnect_customer_owned_account(request.user, request.POST.get("connection_id"))
                messages.success(request, "اتصال حساب اختصاصی قطع و توکن از سرور حذف شد.")
            elif action == "refresh":
                connection = get_object_or_404(
                    TelegramAdsConnection, pk=request.POST.get("connection_id"),
                    customer=profile,
                )
                refresh_connection(connection)
                messages.success(request, "موجودی و وضعیت اتصال از تلگرام به‌روزرسانی شد.")
            elif action == "default":
                set_default_connection(request.user, request.POST.get("connection_id"))
                messages.success(request, "حساب پیش‌فرض کمپین‌های جدید تغییر کرد.")
            else:
                raise ValueError("درخواست نامعتبر است.")
        except (ValueError, TelegramAdsConnection.DoesNotExist) as exc:
            messages.error(request, str(exc) or "عملیات اتصال انجام نشد.")
        except Exception:
            messages.error(request, "ارتباط با تلگرام برقرار نشد یا نتیجه عملیات قابل تأیید نبود.")
        return redirect("accounts:telegram_connection")

    connections = list(
        TelegramAdsConnection.objects.filter(customer=profile)
        .select_related("related_account")
        .order_by("-is_default", "-created_at")
    )
    return render(request, "accounts/telegram_connections.html", {
        "connections": connections,
        "customer_owned_enabled": bool(getattr(settings, "TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED", False)),
        "encryption_ready": len(str(getattr(settings, "TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY", "") or "")) >= 32,
    })
