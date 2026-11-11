from django.shortcuts import get_object_or_404

from apps.accounts.models import CustomerProfile

from .models import Campaign


def get_customer_campaign(customer: CustomerProfile, campaign_id) -> Campaign:
    return get_object_or_404(Campaign, id=campaign_id, customer=customer)
