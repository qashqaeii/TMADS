from __future__ import annotations

from apps.accounts.models import CustomerProfile
from apps.campaigns.metrics import aggregate_portfolio_kpis, build_campaign_list_rows, optimize_campaign_list_queryset
from apps.campaigns.models import Campaign
from apps.finance.models import WalletLedgerEntry
from apps.finance.services import ensure_wallet
from apps.notifications.models import Notification
from apps.support.models import SupportTicket
from apps.telegram_ads.models import TelegramAdsConnection


def dashboard_snapshot(customer: CustomerProfile) -> dict:
    campaigns = optimize_campaign_list_queryset(Campaign.objects.filter(customer=customer))
    rows = build_campaign_list_rows(campaigns)
    portfolio = aggregate_portfolio_kpis(rows)
    wallet = ensure_wallet(customer)
    pending_review = campaigns.filter(status=Campaign.Status.PENDING_REVIEW).count()
    unread = Notification.objects.filter(customer=customer, is_read=False).count()
    return {
        "active_count": portfolio["active_count"],
        "total_campaigns": campaigns.count(),
        "pending_review": pending_review,
        "wallet_available_irr": wallet.available_irr,
        "impressions": int(portfolio["total_impressions"]),
        "clicks": int(portfolio["total_clicks"]),
        "ctr": portfolio["weighted_ctr"],
        "unread_notifications": unread,
    }


def campaign_counts(customer: CustomerProfile) -> dict:
    qs = Campaign.objects.filter(customer=customer)
    return {
        "all": qs.count(),
        "active": qs.filter(status=Campaign.Status.ACTIVE).count(),
        "pending": qs.filter(
            status__in=[
                Campaign.Status.PENDING_REVIEW,
                Campaign.Status.AWAITING_TELEGRAM,
                Campaign.Status.SUBMITTING,
                Campaign.Status.READY_FOR_SUBMISSION,
            ]
        ).count(),
        "paused": qs.filter(status=Campaign.Status.PAUSED).count(),
        "rejected": qs.filter(status=Campaign.Status.REJECTED).count(),
    }


def campaign_page(customer: CustomerProfile, *, filter_key: str = "all", page: int = 0, page_size: int = 5):
    qs = Campaign.objects.filter(customer=customer).order_by("-updated_at")
    if filter_key == "active":
        qs = qs.filter(status=Campaign.Status.ACTIVE)
    elif filter_key == "pending":
        qs = qs.filter(
            status__in=[
                Campaign.Status.PENDING_REVIEW,
                Campaign.Status.AWAITING_TELEGRAM,
                Campaign.Status.SUBMITTING,
                Campaign.Status.READY_FOR_SUBMISSION,
            ]
        )
    elif filter_key == "paused":
        qs = qs.filter(status=Campaign.Status.PAUSED)
    elif filter_key == "rejected":
        qs = qs.filter(status=Campaign.Status.REJECTED)

    total = qs.count()
    start = page * page_size
    items = list(qs[start : start + page_size])
    return items, total, page_size


def wallet_snapshot(customer: CustomerProfile) -> dict:
    wallet = ensure_wallet(customer)
    recent = (
        WalletLedgerEntry.objects.filter(wallet=wallet)
        .order_by("-created_at")[:5]
    )
    return {"wallet": wallet, "recent": list(recent)}


def connections_snapshot(customer: CustomerProfile) -> dict:
    rows = TelegramAdsConnection.objects.filter(customer=customer).order_by("-is_default", "-created_at")
    return {"connections": list(rows)}


def notifications_snapshot(customer: CustomerProfile, *, limit: int = 8) -> dict:
    rows = Notification.objects.filter(customer=customer).order_by("-created_at")[:limit]
    unread = Notification.objects.filter(customer=customer, is_read=False).count()
    return {"items": list(rows), "unread": unread}


def support_snapshot(customer: CustomerProfile) -> dict:
    open_count = SupportTicket.objects.filter(
        customer=customer,
        status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS],
    ).count()
    recent = SupportTicket.objects.filter(customer=customer).order_by("-updated_at")[:5]
    return {"open_count": open_count, "recent": list(recent)}


def reports_snapshot(customer: CustomerProfile) -> dict:
    campaigns = optimize_campaign_list_queryset(Campaign.objects.filter(customer=customer))
    rows = build_campaign_list_rows(campaigns)
    portfolio = aggregate_portfolio_kpis(rows)
    return {
        "active_count": portfolio["active_count"],
        "impressions": int(portfolio["total_impressions"]),
        "clicks": int(portfolio["total_clicks"]),
        "ctr": portfolio["weighted_ctr"],
        "spent_ton": portfolio.get("total_spent_ton"),
    }