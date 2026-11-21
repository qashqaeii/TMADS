from decimal import Decimal

import pytest

from apps.campaigns.models import Campaign
from apps.telegram_ads.models import TelegramAdsConnection
from apps.telegram_ads.services.ad_payload import (
    campaign_daily_budget_limit_ton,
    campaign_initial_budget_ton,
)
from apps.telegram_ads.services.manage_ad import parse_request


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
    assert parse_request("increase_budget", "4.25", currency="EUR") == {"amount": "4.25"}
    assert parse_request("decrease_budget", "2", currency="XTR") == {"amount": "2"}
    with pytest.raises(ValueError):
        parse_request("increase_budget", "2.25", currency="XTR")
    with pytest.raises(ValueError):
        parse_request("increase_budget", "0", currency="TON")
