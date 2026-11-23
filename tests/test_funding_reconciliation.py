from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.finance.funding_reconciliation import reconcile_uncertain_funding_transfer
from apps.campaigns.models import Campaign
from apps.finance.models import AccountFundingTransfer, AdvertisingOrder
from apps.telegram_ads.models import RelatedAccountRequest, TelegramAdsConnection


@pytest.mark.django_db
def test_reconcile_uncertain_funding_transfer(customer_user):
    row = RelatedAccountRequest.objects.create(
        customer=customer_user.customer_profile,
        status=RelatedAccountRequest.Status.PROVISIONED,
        title="Child",
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
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, name="Funded")
    order = AdvertisingOrder.objects.create(
        customer=customer_user.customer_profile,
        campaign_id=campaign.pk,
        status=AdvertisingOrder.Status.SUBMITTING,
        advertising_budget_irr=1_000_000,
        total_irr=1_050_000,
        ton_allocation=Decimal("0.5"),
    )
    transfer = AccountFundingTransfer.objects.create(
        order=order,
        connection=connection,
        direction=AccountFundingTransfer.Direction.MAIN_TO_RELATED,
        status=AccountFundingTransfer.Status.UNCERTAIN,
        amount=Decimal("1.5"),
        currency="TON",
        idempotency_key="reconcile-test-key",
        transaction_id="tx-1",
    )
    manager = User.objects.create_user(username="fund-recon", role=User.Role.ADMIN)
    with patch("apps.finance.funding_reconciliation.TelegramAdsClient") as client:
        client.return_value.get_account_transaction_status.return_value = {
            "status": "completed",
            "transaction_id": "tx-1",
            "amount": "1.5",
            "currency": "TON",
        }
        result = reconcile_uncertain_funding_transfer(transfer.pk, actor=manager)
    assert result.status == AccountFundingTransfer.Status.COMPLETED