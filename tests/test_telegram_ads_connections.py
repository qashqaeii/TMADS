from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.accounts.models import User
from apps.campaigns.models import Campaign, TelegramAdvertisement
from apps.finance.models import AccountFundingTransfer, AdvertisingOrder, Wallet, WalletLedgerEntry
from apps.telegram_ads.models import RelatedAccountRequest, TelegramAdsConnection
from apps.telegram_ads.services.account_connections import (
    campaign_client,
    connect_customer_owned_account,
    decrypt_access_token,
    disconnect_customer_owned_account,
    ensure_platform_managed_connection,
)
from apps.telegram_ads.services.ad_payload import (
    campaign_daily_budget_limit_ton,
    campaign_initial_budget_ton,
)
from apps.telegram_ads.services.manage_ad import parse_request
from apps.telegram_ads.services.submission import submit_campaign_to_telegram


class FakeTelegramClient:
    calls = []

    def __init__(self, token=None, *, account_id=None):
        self.token = token
        self.account_id = account_id
        FakeTelegramClient.calls.append({"token": token, "account_id": account_id})

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
def test_customer_owned_disconnect_clears_token(customer_user, settings):
    settings.TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED = True
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-test-key-" * 4
    with patch("apps.telegram_ads.services.account_connections.TelegramAdsClient", FakeTelegramClient):
        connection = connect_customer_owned_account(customer_user, "disconnect-token-value")
        disconnect_customer_owned_account(customer_user, connection.pk)
    connection.refresh_from_db()
    assert connection.status == TelegramAdsConnection.Status.DISCONNECTED
    assert connection.encrypted_access_token == ""
    assert connection.token_fingerprint == ""
    assert connection.is_default is False


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


@pytest.mark.django_db
def test_tenant_isolation_between_two_customers(customer_user, settings):
    settings.TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED = True
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-test-key-" * 4
    other = User.objects.create_user(username="cust-b", password="pass1234", role=User.Role.CUSTOMER)

    class ScopedClient(FakeTelegramClient):
        def get_account(self):
            account_id = "acct-a" if self.token == "token-a" else "acct-b"
            return {
                "account_id": account_id,
                "currency": "EUR",
                "remaining_budget": "10",
                "title": account_id,
            }

        def get_account_info(self):
            account_id = "acct-a" if self.token == "token-a" else "acct-b"
            return {"account_id": account_id, "title": account_id}

    with patch("apps.telegram_ads.services.account_connections.TelegramAdsClient", ScopedClient):
        conn_a = connect_customer_owned_account(customer_user, "token-a")
        conn_b = connect_customer_owned_account(other, "token-b")

    camp_a = Campaign.objects.create(customer=customer_user.customer_profile, telegram_connection=conn_a, name="A")
    camp_b = Campaign.objects.create(customer=other.customer_profile, telegram_connection=conn_b, name="B")
    assert camp_a.telegram_connection_id != camp_b.telegram_connection_id
    assert list(Campaign.objects.filter(customer=customer_user.customer_profile).values_list("pk", flat=True)) == [camp_a.pk]
    assert list(Campaign.objects.filter(customer=other.customer_profile).values_list("pk", flat=True)) == [camp_b.pk]


@pytest.mark.django_db
def test_customer_owned_submission_never_creates_tmads_order_or_wallet(customer_user, settings):
    settings.TELEGRAM_ADS_WRITE_ENABLED = True
    settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED = True
    settings.TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED = True
    connection = TelegramAdsConnection.objects.create(
        customer=customer_user.customer_profile,
        connection_type=TelegramAdsConnection.Type.CUSTOMER_OWNED,
        status=TelegramAdsConnection.Status.CONNECTED,
        remote_account_id="customer-owned-77",
        account_title="Personal Telegram Ads",
        currency="EUR",
        remaining_budget=100,
        encrypted_access_token="encrypted-only",
        token_fingerprint="b" * 64,
        is_default=True,
    )
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        telegram_connection=connection,
        name="Personal account campaign",
        status=Campaign.Status.READY_FOR_SUBMISSION,
        budget_currency="EUR",
        account_budget_amount=Decimal("5.00"),
        account_daily_budget_limit=Decimal("1.00"),
        ad_settings={"remote_initial_status": "on_hold", "is_paused": True},
    )

    def claim(campaign_id):
        Campaign.objects.filter(pk=campaign_id).update(status=Campaign.Status.SUBMITTING)
        return Campaign.objects.get(pk=campaign_id)

    def create_remote_ad(current, *, mode):
        return TelegramAdvertisement.objects.create(
            campaign=current,
            remote_ad_id="987654321",
            remote_account_id=current.telegram_connection.remote_account_id,
            remote_status="on_hold",
        )

    with (
        patch("apps.telegram_ads.services.submission._claim_customer_owned_submission", side_effect=claim),
        patch("apps.telegram_ads.services.submission.execute_create_ad", side_effect=create_remote_ad),
    ):
        result = submit_campaign_to_telegram(campaign)

    assert result.remote_ad_id == "987654321"
    assert result.remote_account_id == "customer-owned-77"
    assert not AdvertisingOrder.objects.filter(campaign_id=campaign.pk).exists()
    wallet = Wallet.objects.get(customer=customer_user.customer_profile)
    assert wallet.available_irr == 0
    assert wallet.reserved_irr == 0
    assert not WalletLedgerEntry.objects.filter(wallet=wallet).exists()
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.AWAITING_TELEGRAM


@pytest.mark.django_db
def test_funding_transfer_idempotency_key_is_unique(customer_user):
    row = RelatedAccountRequest.objects.create(
        customer=customer_user.customer_profile,
        status=RelatedAccountRequest.Status.PROVISIONED,
        title="Managed",
        consent_at=timezone.now(),
        main_account_id="main-1",
        remote_account_id="child-9",
    )
    connection = TelegramAdsConnection.objects.create(
        customer=customer_user.customer_profile,
        connection_type=TelegramAdsConnection.Type.PLATFORM_MANAGED,
        status=TelegramAdsConnection.Status.CONNECTED,
        remote_account_id="child-9",
        related_account=row,
        currency="TON",
        remaining_budget=0,
        is_default=True,
    )
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        telegram_connection=connection,
        name="Managed funded",
        status=Campaign.Status.PAID,
        budget_irr=10_000_000,
    )
    order = AdvertisingOrder.objects.create(
        customer=customer_user.customer_profile,
        campaign_id=campaign.pk,
        status=AdvertisingOrder.Status.PAID,
        advertising_budget_irr=10_000_000,
        total_irr=10_000_000,
        ton_allocation=Decimal("5.00"),
    )
    AccountFundingTransfer.objects.create(
        order=order,
        connection=connection,
        amount=Decimal("5.00"),
        currency="TON",
        idempotency_key=f"tmads-fund-{order.pk}",
        status=AccountFundingTransfer.Status.COMPLETED,
    )
    with pytest.raises(IntegrityError):
        AccountFundingTransfer.objects.create(
            order=order,
            connection=connection,
            amount=Decimal("5.00"),
            currency="TON",
            idempotency_key=f"tmads-fund-{order.pk}",
            status=AccountFundingTransfer.Status.EXECUTING,
        )


@pytest.mark.django_db
def test_same_remote_ad_id_allowed_on_different_accounts(customer_user):
    other = User.objects.create_user(username="cust-c", password="pass1234", role=User.Role.CUSTOMER)
    conn_a = TelegramAdsConnection.objects.create(
        customer=customer_user.customer_profile,
        connection_type=TelegramAdsConnection.Type.CUSTOMER_OWNED,
        status=TelegramAdsConnection.Status.CONNECTED,
        remote_account_id="acct-1",
        currency="EUR",
        remaining_budget=10,
        encrypted_access_token="enc-a",
        token_fingerprint="c" * 64,
        is_default=True,
    )
    conn_b = TelegramAdsConnection.objects.create(
        customer=other.customer_profile,
        connection_type=TelegramAdsConnection.Type.CUSTOMER_OWNED,
        status=TelegramAdsConnection.Status.CONNECTED,
        remote_account_id="acct-2",
        currency="EUR",
        remaining_budget=10,
        encrypted_access_token="enc-b",
        token_fingerprint="d" * 64,
        is_default=True,
    )
    camp_a = Campaign.objects.create(customer=customer_user.customer_profile, telegram_connection=conn_a, name="A")
    camp_b = Campaign.objects.create(customer=other.customer_profile, telegram_connection=conn_b, name="B")
    TelegramAdvertisement.objects.create(
        campaign=camp_a, remote_ad_id="111", remote_account_id="acct-1",
    )
    TelegramAdvertisement.objects.create(
        campaign=camp_b, remote_ad_id="111", remote_account_id="acct-2",
    )
    assert TelegramAdvertisement.objects.filter(remote_ad_id="111").count() == 2


@pytest.mark.django_db
def test_legacy_campaign_without_connection_still_uses_platform_client(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="Legacy central campaign",
    )
    FakeTelegramClient.calls = []
    with patch("apps.telegram_ads.services.account_connections.TelegramAdsClient", FakeTelegramClient):
        client = campaign_client(campaign)
    assert client.token is None
    assert client.account_id is None
    assert FakeTelegramClient.calls == [{"token": None, "account_id": None}]


@pytest.mark.django_db
def test_customer_owned_campaign_budget_is_in_account_currency(customer_user):
    connection = TelegramAdsConnection.objects.create(
        customer=customer_user.customer_profile,
        connection_type=TelegramAdsConnection.Type.CUSTOMER_OWNED,
        status=TelegramAdsConnection.Status.CONNECTED,
        remote_account_id="customer-account-9",
        account_title="Customer account",
        currency="EUR",
        remaining_budget=Decimal("80.00"),
        encrypted_access_token="encrypted-token",
        token_fingerprint="a" * 64,
        is_default=True,
    )
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        telegram_connection=connection,
        name="EUR campaign",
        account_budget_amount=Decimal("12.50"),
        account_daily_budget_limit=Decimal("3.25"),
        budget_currency="EUR",
    )

    assert Decimal(str(campaign_initial_budget_ton(campaign))) == Decimal("12.5")
    assert Decimal(str(campaign_daily_budget_limit_ton(campaign))) == Decimal("3.25")
    assert campaign.budget_irr == 0
    assert campaign.daily_cap_irr == 0


def test_customer_owned_budget_requests_use_currency_precision():
    assert parse_request("edit_cpm", "4.25", currency="EUR") == {"cpm": "4.25"}
    assert parse_request("edit_daily_limit", "2", currency="XTR") == {"daily_budget_limit": "2"}
    with pytest.raises(ValueError):
        parse_request("edit_cpm", "2.25", currency="XTR")
    with pytest.raises(ValueError):
        parse_request("edit_cpm", "0", currency="TON")


@pytest.mark.django_db
def test_on_hold_payload_flag_preserved_for_customer_owned(customer_user):
    from apps.campaigns.models import AdCreative, CampaignTargeting
    from apps.telegram_ads.services.ad_payload import build_create_ad_payload

    connection = TelegramAdsConnection.objects.create(
        customer=customer_user.customer_profile,
        connection_type=TelegramAdsConnection.Type.CUSTOMER_OWNED,
        status=TelegramAdsConnection.Status.CONNECTED,
        remote_account_id="hold-acct",
        currency="EUR",
        remaining_budget=Decimal("20"),
        encrypted_access_token="enc",
        token_fingerprint="e" * 64,
        is_default=True,
    )
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        telegram_connection=connection,
        name="Paused launch",
        objective=Campaign.Objective.CHANNEL,
        destination="https://t.me/example",
        placement=Campaign.Placement.CHANNEL_POST,
        target_type=Campaign.TargetType.CHANNELS,
        account_budget_amount=Decimal("5"),
        account_daily_budget_limit=Decimal("1"),
        budget_currency="EUR",
        cpm_bid=Decimal("1.00"),
        wizard_version=2,
        ad_settings={"remote_initial_status": "on_hold", "is_paused": True, "terms_accepted": True},
    )
    CampaignTargeting.objects.create(
        campaign=campaign, config={"channel_mode": "language", "language_codes": ["fa"]},
    )
    AdCreative.objects.create(campaign=campaign, ad_text="متن تست", title="Paused launch")
    payload = build_create_ad_payload(campaign, include_initial_budget=True)
    assert payload.get("is_paused") is True
