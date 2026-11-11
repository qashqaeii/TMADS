import pytest
from django.urls import reverse

from apps.campaigns.models import Campaign
from apps.finance.models import Invoice
from apps.finance.services import credit_wallet_deposit, ensure_wallet


@pytest.mark.django_db
def test_wizard_creates_quote(client, customer_user):
    client.login(username=customer_user.username, password="pass1234")
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, name="تست")
    campaign.budget_irr = 1_000_000
    campaign.wizard_step = 4
    campaign.wizard_version = 2
    campaign.target_type = "channels"
    campaign.placement = "channel_post"
    campaign.destination = "https://t.me/test"
    campaign.save()
    url = reverse("campaigns:wizard", kwargs={"campaign_id": campaign.id})
    response = client.post(url, {"action": "next", "budget_toman": "100"})
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.AWAITING_PAYMENT
    assert response.status_code in (302, 200)


@pytest.mark.django_db
def test_pay_from_wallet_moves_to_pending_review_and_invoice(client, customer_user):
    wallet = ensure_wallet(customer_user.customer_profile)
    credit_wallet_deposit(wallet, 5_000_000, "seed-1")
    from apps.campaigns.models import AdCreative, CampaignTargeting

    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="paid-c",
        status=Campaign.Status.AWAITING_PAYMENT,
        budget_irr=1_000_000,
        wizard_step=5,
        wizard_version=2,
        target_type="channels",
        placement="channel_post",
        destination="https://t.me/test",
        cpm_bid=1,
        ad_settings={"terms_accepted": True},
    )
    AdCreative.objects.create(campaign=campaign, ad_text="متن تبلیغ تست")
    CampaignTargeting.objects.create(campaign=campaign, config={"language_codes": ["fa"]})
    from apps.campaigns.views import _create_quote

    _create_quote(campaign)
    client.login(username=customer_user.username, password="pass1234")
    url = reverse("campaigns:wizard", kwargs={"campaign_id": campaign.id})
    client.post(url, {"action": "pay", "terms_accepted": "1"})
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.PENDING_REVIEW
    assert Invoice.objects.filter(customer=customer_user.customer_profile).exists()
