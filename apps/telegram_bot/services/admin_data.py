from __future__ import annotations

from django.db.models import Sum
from django.utils import timezone

from apps.accounts.models import CustomerProfile
from apps.campaigns.models import Campaign, RemoteAdOperation
from apps.finance.models import AccountFundingTransfer, AdvertisingOrder, RefundRequest, Wallet
from apps.support.models import SupportTicket


def recent_open_tickets(limit: int = 5):
    return list(
        SupportTicket.objects.filter(
            status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS],
        ).select_related("customer")
        .order_by("-updated_at")[:limit]
    )


def ops_overview() -> dict:
    return {
        "today": timezone.localdate(),
        "remote_pending": RemoteAdOperation.objects.filter(status=RemoteAdOperation.Status.PENDING).count(),
        "customer_count": CustomerProfile.objects.count(),
        "order_count": AdvertisingOrder.objects.count(),
        "pending_campaigns": Campaign.objects.filter(status=Campaign.Status.PENDING_REVIEW).count(),
        "open_refunds": RefundRequest.objects.filter(
            status__in=[RefundRequest.Status.OPEN, RefundRequest.Status.REVIEW],
        ).count(),
        "uncertain_funding": AccountFundingTransfer.objects.filter(
            status=AccountFundingTransfer.Status.UNCERTAIN,
        ).count(),
        "wallet_liabilities": Wallet.objects.aggregate(
            available=Sum("available_irr"),
            reserved=Sum("reserved_irr"),
        ),
        "open_tickets": SupportTicket.objects.filter(
            status__in=[SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS],
        ).count(),
    }