from unittest.mock import patch

import pytest
from django.urls import reverse
from apps.campaigns.models import Campaign
from apps.campaigns.views import _create_quote, _quote_valid
from apps.finance.exceptions import StaleRateError
from apps.finance.models import AdvertisingOrder


@pytest.mark.django_db
def test_quote_failure_never_creates_payable_order(customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, budget_irr=2_000_000)
    with patch("apps.finance.services.campaign_pricing.build_campaign_quote", side_effect=StaleRateError("stale")):
        with pytest.raises(StaleRateError):
            _create_quote(campaign)
    assert not AdvertisingOrder.objects.filter(campaign_id=campaign.id).exists()


@pytest.mark.django_db
def test_budget_change_invalidates_locked_quote(customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, budget_irr=2_000_000)
    _create_quote(campaign)
    order = AdvertisingOrder.objects.get(campaign_id=campaign.id)
    assert _quote_valid(campaign, order, order.quote)
    campaign.budget_irr += 500_000
    assert not _quote_valid(campaign, order, order.quote)


@pytest.mark.django_db
def test_paid_campaign_cannot_autosave_or_open_studio(client, customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, status=Campaign.Status.PENDING_REVIEW, name="Locked")
    client.force_login(customer_user)
    assert client.post(reverse("campaigns:autosave", args=[campaign.id]), {"campaign_name": "changed"}).status_code == 409
    assert client.get(reverse("campaigns:wizard", args=[campaign.id])).status_code == 302
    campaign.refresh_from_db()
    assert campaign.name == "Locked"
