"""Private SMS operations workspace. No sending or secret exposure."""
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.accounts.permissions import staff_ops_required
from apps.notifications.faraz import configured, get_balance
from apps.notifications.models import SmsContact, SmsOtp, SmsOutbox

PURPOSES = {"verify_mobile": "تأیید موبایل", "wallet_credit": "شارژ کیف پول",
            "budget_low": "کاهش بودجه", "campaign_status": "نتیجه بررسی کمپین"}


@never_cache
@login_required
@staff_ops_required
@require_http_methods(["GET", "POST"])
def sms_workspace(request):
    totals = dict(SmsOutbox.objects.values("status").annotate(count=Count("pk")).values_list("status", "count"))
    status = request.GET.get("status", "")
    rows = SmsOutbox.objects.all()
    if status in SmsOutbox.Status.values:
        rows = rows.filter(status=status)
    else:
        status = ""
    page = Paginator(rows, 30).get_page(request.GET.get("page", 1))
    items = [{"purpose": PURPOSES.get(r.purpose, r.purpose), "status": r.get_status_display(),
              "state": r.status, "phone": r.phone[:4]+"•••••"+r.phone[-2:],
              "time": r.created_at, "ref": r.provider_id, "error": r.error_code} for r in page]
    balance, balance_error = None, ""
    if request.method == "POST" and request.POST.get("action") == "balance":
        balance, balance_error = get_balance()
    return render(request, "operations/sms.html", {
        "enabled": settings.SMS_ENABLED, "provider": settings.SMS_PROVIDER,
        "patterns": [{"label": label, "ready": configured(key) and settings.SMS_PROVIDER == "faraz"}
                     for key, label in PURPOSES.items()],
        "contacts": SmsContact.objects.filter(enabled=True).count(),
        "otp_requests": SmsOtp.objects.count(),
        "queued": totals.get("queued", 0)+totals.get("sending", 0),
        "accepted": totals.get("accepted", 0), "attention": totals.get("failed", 0)+totals.get("unknown", 0),
        "items": items, "page": page, "status": status, "choices": SmsOutbox.Status.choices,
        "balance": balance, "balance_error": bool(balance_error),
    })
