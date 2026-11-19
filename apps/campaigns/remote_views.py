"""Customer requests for managing an existing Telegram advertisement.

This path never writes to Telegram or debits a wallet. Operations require a
separate authenticated, audited operator decision.
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import customer_required
from apps.campaigns.models import Campaign, RemoteAdOperation, TelegramAdvertisement
from apps.campaigns.ownership import get_customer_campaign
from apps.core.models import AuditLog

OPEN_STATES = (
    RemoteAdOperation.Status.PENDING,
    RemoteAdOperation.Status.EXECUTING,
    RemoteAdOperation.Status.UNCERTAIN,
)
ACTIONS = {
    RemoteAdOperation.Action.PAUSE: ("توقف تبلیغ", "pause", "none"),
    RemoteAdOperation.Action.RESUME: ("ادامه تبلیغ", "play", "none"),
    RemoteAdOperation.Action.REVIEW: ("ارسال برای بررسی", "clipboard-check", "none"),
    RemoteAdOperation.Action.EDIT_CPM: ("تغییر CPM", "gauge", "cpm"),
    RemoteAdOperation.Action.EDIT_DAILY_LIMIT: ("تغییر سقف روزانه", "calendar-clock", "daily_limit"),
    RemoteAdOperation.Action.EDIT_TITLE: ("تغییر عنوان داخلی", "pencil", "title"),
    RemoteAdOperation.Action.INCREASE_BUDGET: ("درخواست افزایش بودجه", "plus-circle", "budget"),
    RemoteAdOperation.Action.DECREASE_BUDGET: ("درخواست کاهش بودجه", "minus-circle", "budget"),
}
# A remote account or ad must always be verified before fulfilling a request.
# Budget requests do not reserve/debit/release funds at this stage.


def parse_request(action, raw):
    if action not in ACTIONS:
        raise ValueError("عملیات انتخاب‌شده معتبر نیست.")
    field = ACTIONS[action][2]
    if field == "none":
        return {}
    if field == "title":
        title = (raw or "").strip()
        if not title or len(title.encode("utf-8")) > 128:
            raise ValueError("عنوان باید بین ۱ تا ۱۲۸ بایت باشد.")
        return {"title": title}
    try:
        value = Decimal(str(raw).strip())
        if (not value.is_finite() or value <= 0 or value > Decimal("99999999.99")
                or value != value.quantize(Decimal("0.01"))):
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("مقدار باید یک عدد مثبت با حداکثر دو رقم اعشار TON باشد.") from None
    return {field: str(value)}


@login_required
@customer_required
@require_http_methods(["GET", "POST"])
def remote_management(request, campaign_id):
    campaign = get_customer_campaign(request.user.customer_profile, campaign_id)
    ad = campaign.remote_ads.exclude(remote_ad_id="").order_by("-updated_at").first()
    if ad is None:
        messages.error(request, "هنوز تبلیغ متصل به تلگرام برای این کمپین وجود ندارد.")
        return redirect("campaigns:detail", campaign_id=campaign.id)

    if request.method == "POST":
        try:
            payload = parse_request(request.POST.get("action", ""), request.POST.get("value", ""))
            with transaction.atomic():
                campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
                ad = TelegramAdvertisement.objects.select_for_update().get(pk=ad.pk, campaign=campaign)
                if campaign.status in {Campaign.Status.SUBMITTING, Campaign.Status.RECONCILIATION,
                                       Campaign.Status.CANCELLED, Campaign.Status.FAILED}:
                    raise ValueError("این کمپین در حال حاضر اجازه ثبت درخواست تغییر ندارد.")
                if ad.operations.filter(status__in=OPEN_STATES).exists():
                    raise ValueError("درخواست قبلی هنوز تعیین تکلیف نشده است.")
                action = request.POST.get("action", "")
                op = RemoteAdOperation.objects.create(
                    advertisement=ad, action=action, request_payload=payload,
                    status=RemoteAdOperation.Status.PENDING,
                )
                AuditLog.objects.create(
                    actor=request.user, action="remote_ad.operation_requested",
                    entity_type="campaign", entity_id=campaign.pk,
                    new_state={"operation_id": str(op.pk), "action": op.action},
                )
            messages.success(request, "درخواست ثبت شد و برای بررسی اپراتور ارسال می‌شود. تغییر در تلگرام انجام نشده است.")
        except (ValueError, IntegrityError) as exc:
            messages.error(request, str(exc) if isinstance(exc, ValueError) else "درخواست مشابهی در جریان است.")
        return redirect("campaigns:remote_management", campaign_id=campaign.pk)

    operations = list(ad.operations.order_by("-created_at")[:15])
    has_open = any(op.status in OPEN_STATES for op in operations)
    return render(request, "campaigns/remote_management.html", {
        "campaign": campaign,
        "ad": ad,
        "operations": operations,
        "has_open": has_open,
        "actions": [(key, label, icon, field) for key, (label, icon, field) in ACTIONS.items()],
        "can_request": campaign.status not in {
            Campaign.Status.SUBMITTING, Campaign.Status.RECONCILIATION,
            Campaign.Status.CANCELLED, Campaign.Status.FAILED,
        } and not has_open,
    })
