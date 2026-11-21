from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.campaigns.models import Campaign
from apps.telegram_ads.models import RelatedAccountRequest, TelegramAdsConnection
from apps.telegram_ads.services.account_connections import (
    campaign_client,
    connect_customer_owned_account,
    decrypt_access_token,
    ensure_platform_managed_connection,
)


class FakeTelegramClient:
    calls = []

    def __init__(self, token=None, *, account_id=None):
        self.token = token
        self.account_id = account_id
        self.calls.append({"token": token, "account_id": account_id})

    def get_account(self):
        account_id = self.account_id or ("personal-42" if self.token else "main-1")
        return {
            "account_id": account_id,
            "currency": "EUR" if self.token else "TON",
            "remaining_budget": "25.50" if self.token else "100.00",
            "title": "Verified account",
        }

    def get_account_info(self):
        account_id = self.account_id or ("personal-42" if self.token else "main-1")
        return {"account_id": account_id, "title": "Verified account"}


@pytest.mark.django_db
def test_customer_owned_token_is_verified_and_encrypted(customer_user, settings):
    settings.TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED = True
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-test-key-" * 4
    FakeTelegramClient.calls = []
    token = "telegram-secret-token-that-must-never-be-stored-plaintext"

    with patch("apps.telegram_ads.services.account_connections.TelegramAdsClient", FakeTelegramClient):
        connection = connect_customer_owned_account(customer_user, token)

    connection.refresh_from_db()
    assert connection.connection_type == TelegramAdsConnection.Type.CUSTOMER_OWNED
    assert connection.status == TelegramAdsConnection.Status.CONNECTED
    assert connection.remote_account_id == "personal-42"
    assert connection.currency == "EUR"
    assert connection.remaining_budget == Decimal("25.50")
    assert connection.is_default is True
    assert token not in connection.encrypted_access_token
    assert connection.token_fingerprint
    assert decrypt_access_token(connection) == token
    assert connection.related_account_id is None


@pytest.mark.django_db
def test_same_customer_token_cannot_be_shared_with_another_customer(customer_user, settings):
    settings.TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED = True
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-test-key-" * 4
    other = User.objects.create_user(username="cust2", password="pass1234", role=User.Role.CUSTOMER)
    token = "one-token-one-owner-only"

    with patch("apps.telegram_ads.services.account_connections.TelegramAdsClient", FakeTelegramClient):
        connect_customer_owned_account(customer_user, token)
        with pytest.raises(ValueError, match="قبلاً"):
            connect_customer_owned_account(other, token)


@pytest.mark.django_db
def test_campaign_client_uses_customer_owned_token_not_platform_token(customer_user, settings):
    settings.TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED = True
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-test-key-" * 4
    token = "customer-private-api-token"
    with patch("apps.telegram_ads.services.account_connections.TelegramAdsClient", FakeTelegramClient):
        connection = connect_customer_owned_account(customer_user, token)
        campaign = Campaign.objects.create(
            customer=customer_user.customer_profile,
            telegram_connection=connection,
            name="Customer-owned campaign",
        )
        FakeTelegramClient.calls = []
        client = campaign_client(campaign)

    assert client.token == token
    assert client.account_id is None
    assert FakeTelegramClient.calls == [{"token": token, "account_id": None}]


@pytest.mark.django_db
def test_managed_connection_is_bound_to_verified_child_account(customer_user):
    row = RelatedAccountRequest.objects.create(
        customer=customer_user.customer_profile,
        status=RelatedAccountRequest.Status.PROVISIONED,
        title="Customer child account",
        consent_at=timezone.now(),
        main_account_id="main-1",
        remote_account_id="child-42",
    )
    FakeTelegramClient.calls = []
    with patch("apps.telegram_ads.services.account_connections.TelegramAdsClient", FakeTelegramClient):
        connection = ensure_platform_managed_connection(row)

    assert connection.connection_type == TelegramAdsConnection.Type.PLATFORM_MANAGED
    assert connection.remote_account_id == "child-42"
    assert connection.related_account_id == row.pk
    assert connection.currency == "TON"
    assert connection.encrypted_access_token == ""
    assert connection.token_fingerprint == ""
    assert FakeTelegramClient.calls == [
        {"token": None, "account_id": None},
        {"token": None, "account_id": "child-42"},
    ]


@pytest.mark.django_db
def test_managed_campaign_client_is_scoped_to_its_child_account(customer_user):
    row = RelatedAccountRequest.objects.create(
        customer=customer_user.customer_profile,
        status=RelatedAccountRequest.Status.PROVISIONED,
        title="Customer child account",
        consent_at=timezone.now(),
        main_account_id="main-1",
        remote_account_id="child-42",
    )
    with patch("apps.telegram_ads.services.account_connections.TelegramAdsClient", FakeTelegramClient):
        connection = ensure_platform_managed_connection(row)
        campaign = Campaign.objects.create(
            customer=customer_user.customer_profile,
            telegram_connection=connection,
            name="Managed campaign",
        )
        FakeTelegramClient.calls = []
        client = campaign_client(campaign)

    assert client.token is None
    assert client.account_id == "child-42"
    assert FakeTelegramClient.calls == [{"token": None, "account_id": "child-42"}]
