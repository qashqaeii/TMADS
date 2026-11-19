from uuid import UUID

from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.accounts.models import CustomerProfile

from .models import Campaign


def get_customer_campaign(customer: CustomerProfile, campaign_id) -> Campaign:
    try:
        campaign_id = UUID(str(campaign_id))
    except (TypeError, ValueError, AttributeError):
        raise Http404("کمپین یافت نشد.") from None
    return get_object_or_404(Campaign, id=campaign_id, customer=customer)
