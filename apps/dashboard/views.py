import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.accounts.permissions import customer_required
from apps.campaigns.live_data import customer_has_linked_ads
from apps.campaigns.metrics import aggregate_portfolio_kpis, build_campaign_list_rows, optimize_campaign_list_queryset
from apps.campaigns.models import Campaign, CampaignStatusHistory
from apps.finance.services import ensure_wallet
from apps.notifications.models import Notification


@login_required
@customer_required
def home(request):
    customer = request.user.customer_profile
    campaigns = optimize_campaign_list_queryset(Campaign.objects.filter(customer=customer))
    portfolio_rows = build_campaign_list_rows(campaigns)
    portfolio = aggregate_portfolio_kpis(portfolio_rows)
    active_count = portfolio["active_count"]

    wallet = ensure_wallet(customer)

    recent_rows = sorted(portfolio_rows, key=lambda r: r.campaign.updated_at, reverse=True)[:6]
    activity = (
        CampaignStatusHistory.objects.filter(campaign__customer=customer)
        .select_related("campaign")
        .order_by("-created_at")[:20]
    )
    unread = Notification.objects.filter(customer=customer, is_read=False).count()

    impressions = int(portfolio["total_impressions"])
    clicks = int(portfolio["total_clicks"])
    ctr = portfolio["weighted_ctr"]

    from apps.campaigns.analytics import portfolio_timeseries

    chart = portfolio_timeseries(customer, days=30)
    has_chart = bool(chart.get("dates"))
    has_linked_ads = customer_has_linked_ads(customer)

    ton_rate_display = None
    try:
        from apps.finance.services.ton_exchange_rate import get_ui_rate_snapshot

        ton_rate_display = get_ui_rate_snapshot()
    except Exception:
        pass

    return render(
        request,
        "dashboard/home.html",
        {
            "ton_rate_display": ton_rate_display,
            "active_count": active_count,
            "total_campaigns": campaigns.count(),
            "impressions": impressions,
            "clicks": clicks,
            "ctr": ctr,
            "portfolio": portfolio,
            "wallet": wallet,
            "recent_rows": recent_rows,
            "activity": activity,
            "unread_notifications": unread,
            "chart_json": json.dumps(chart, ensure_ascii=False),
            "has_chart": has_chart,
            "has_linked_ads": has_linked_ads,
            "ga_live_boot": True,
            "ga_live_stats": has_linked_ads,
        },
    )


@login_required
@customer_required
@require_GET
def live_gram_rate(request):
    """HTML fragment: fresh Gram/TON rate chip for live UI panels."""
    ton_rate_display = None
    try:
        from apps.finance.services.ton_exchange_rate import get_ui_rate_snapshot

        ton_rate_display = get_ui_rate_snapshot(refresh=True)
    except Exception:
        ton_rate_display = None
    return render(
        request,
        "includes/live_gram_rate_chip.html",
        {"ton_rate_display": ton_rate_display},
    )


@login_required
@customer_required
def notifications(request):
    qs = Notification.objects.filter(customer=request.user.customer_profile)
    if request.method == "POST":
        qs.filter(is_read=False).update(is_read=True)
    return render(request, "dashboard/notifications.html", {"notifications": qs[:50]})
