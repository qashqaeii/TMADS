from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

from apps.accounts.permissions import customer_required

from .config import bot_runtime_enabled
from .services.link import LINK_TTL_MINUTES, create_link_token


@login_required
@customer_required
@require_POST
def create_link_token_view(request):
    if not bot_runtime_enabled():
        messages.error(request, "ربات تلگرام در حال حاضر غیرفعال است.")
        return redirect("accounts:profile")
    raw = create_link_token(request.user.customer_profile)
    request.session["telegram_bot_link_token"] = raw
    request.session["telegram_bot_link_expires_min"] = LINK_TTL_MINUTES
    messages.success(
        request,
        f"کد اتصال ربات ساخته شد (اعتبار {LINK_TTL_MINUTES} دقیقه). در تلگرام دستور /start link_کد را بزنید.",
    )
    return redirect("accounts:profile")