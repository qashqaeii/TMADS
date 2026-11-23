"""Operator-only central Telegram Ads token registration (write-only)."""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.models import TelegramAdsPlatformCredential
from apps.telegram_ads.services.platform_credentials import configure_platform_token


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def platform_api_token(request):
    if not request.user.is_platform_manager:
        raise PermissionDenied
    if request.method == "POST":
        try:
            configure_platform_token(request.user, request.POST.get("api_token", ""))
            messages.success(request, "توکن حساب مرکزی با هویت تأییدشده و به‌صورت رمزنگاری‌شده ذخیره شد.")
        except ValueError as exc:
            messages.error(request, str(exc))
        except TelegramAdsError:
            messages.error(request, "تأیید توکن حساب مرکزی در Telegram Ads ناموفق بود.")
        return redirect("operations:platform_api_token")

    credential = TelegramAdsPlatformCredential.objects.filter(slot="primary").first()
    return render(request, "operations/platform_api_token.html", {
        "credential": credential,
        "encryption_ready": len(str(getattr(settings, "TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY", "") or "")) >= 32,
    })
