from __future__ import annotations

from apps.accounts.models import CustomerProfile

from .models import Notification


def notify_customer(
    customer: CustomerProfile,
    title: str,
    body: str = "",
    *,
    level: str = "info",
    related_campaign_id=None,
) -> Notification:
    return Notification.objects.create(
        customer=customer,
        title=title,
        body=body,
        level=level,
        related_campaign_id=related_campaign_id,
    )
