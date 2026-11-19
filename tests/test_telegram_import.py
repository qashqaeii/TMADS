import pytest

from apps.accounts.models import User
from apps.campaigns.models import Campaign, TelegramAdvertisement
from apps.telegram_ads.services.import_campaigns import (
    import_remote_campaigns_for_customer,
    prune_empty_draft_campaigns,
)


@pytest.mark.django_db
def test_import_creates_hyper_tunnel_campaign(monkeypatch):
    user = User.objects.create_user(username="su", password="x", is_superuser=True)
    customer = user.customer_profile

    Campaign.objects.create(customer=customer, name="کمپین جدید", status=Campaign.Status.DRAFT)

    def fake_list(self):
        return [
            {
                "ad_id": 99,
                "title": "hyper campaign 2",
                "promote_url": "https://t.me/HyperTunnelbot",
                "status": "stopped",
                "placement": "search",
                "views": 100,
                "clicks": 5,
                "actions": 3,
                "cpm": 5.0,
                "text": "sample",
            }
        ]

    monkeypatch.setattr(
        "apps.telegram_ads.services.import_campaigns.TelegramAdsClient.list_advertisements",
        fake_list,
    )

    prune_empty_draft_campaigns(customer)
    created, updated, skipped = import_remote_campaigns_for_customer(
        customer, fetch_statistics=False
    )

    assert created == 1
    assert Campaign.objects.filter(customer=customer).count() == 1
    camp = Campaign.objects.get(customer=customer)
    assert camp.name == "hyper campaign 2"
    assert camp.destination == "https://t.me/HyperTunnelbot"
    assert camp.objective == Campaign.Objective.BOT
    assert TelegramAdvertisement.objects.filter(remote_ad_id="99").exists()


@pytest.mark.django_db
def test_prune_preserves_draft_content():
    user = User.objects.create_user(username="prune-safe", password="x")
    campaign = Campaign.objects.create(customer=user.customer_profile, name="کمپین جدید", destination="https://t.me/example")
    assert prune_empty_draft_campaigns(user.customer_profile) == 0
    assert Campaign.objects.filter(pk=campaign.pk).exists()
