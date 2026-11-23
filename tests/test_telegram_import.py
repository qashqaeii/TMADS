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
def test_import_uses_connection_scoped_client(monkeypatch, customer_user):
    from apps.telegram_ads.models import TelegramAdsConnection

    connection = TelegramAdsConnection.objects.create(
        customer=customer_user.customer_profile,
        connection_type=TelegramAdsConnection.Type.CUSTOMER_OWNED,
        status=TelegramAdsConnection.Status.CONNECTED,
        remote_account_id="import-own",
        currency="TON",
        remaining_budget=1,
        encrypted_access_token="enc",
        token_fingerprint="a" * 64,
        is_default=True,
    )
    calls = {"list": 0}

    def fake_list(self):
        calls["list"] += 1
        return [{"ad_id": 11, "title": "scoped", "promote_url": "https://t.me/x", "status": "active", "currency": "TON"}]

    monkeypatch.setattr(
        "apps.telegram_ads.services.import_campaigns.connection_client",
        lambda conn: type("C", (), {"list_advertisements": fake_list})(),
    )
    created, _, _ = import_remote_campaigns_for_customer(
        customer_user.customer_profile, connection=connection, fetch_statistics=False,
    )
    assert created == 1
    camp = Campaign.objects.get(customer=customer_user.customer_profile)
    assert camp.telegram_connection_id == connection.pk
    ad = TelegramAdvertisement.objects.get(remote_ad_id="11")
    assert ad.remote_account_id == "import-own"


@pytest.mark.django_db
def test_prune_preserves_draft_content():
    user = User.objects.create_user(username="prune-safe", password="x")
    campaign = Campaign.objects.create(customer=user.customer_profile, name="کمپین جدید", destination="https://t.me/example")
    assert prune_empty_draft_campaigns(user.customer_profile) == 0
    assert Campaign.objects.filter(pk=campaign.pk).exists()
