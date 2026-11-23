from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.campaigns.models import Campaign, RemoteAdOperation, TelegramAdvertisement
from apps.finance.budget_management import preview_budget, submit_budget_proposal
from apps.finance.models import AccountFundingTransfer, WalletLedgerEntry
from apps.finance.services import ensure_wallet
from apps.finance.managed_budget_increase import outstanding_budget_reservation
from apps.telegram_ads.models import RelatedAccountRequest, TelegramAdsConnection
from apps.telegram_ads.services.manage_ad import execute_operation


@pytest.mark.django_db
def test_managed_increase_reserves_funds_transfers_and_settles(customer_user, settings):
    settings.TELEGRAM_ADS_WRITE_ENABLED = settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED = True
    wallet = ensure_wallet(customer_user.customer_profile)
    wallet.available_irr = 200_000_000
    wallet.save(update_fields=["available_irr"])
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
        remaining_budget=Decimal("1"),
        is_default=True,
    )
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        telegram_connection=connection,
        status=Campaign.Status.ACTIVE,
        destination="https://t.me/example",
        budget_irr=1_000_000,
    )
    ad = TelegramAdvertisement.objects.create(
        campaign=campaign,
        remote_ad_id="88",
        remote_account_id="child-9",
        remote_status_raw={"currency": "TON", "remaining_budget": "1"},
    )
    from apps.finance.models import AdvertisingOrder

    AdvertisingOrder.objects.create(
        customer=customer_user.customer_profile,
        campaign_id=campaign.pk,
        status=AdvertisingOrder.Status.COMPLETED,
        advertising_budget_irr=1_000_000,
        total_irr=1_050_000,
        ton_allocation=Decimal("0.5"),
    )
    _, token = preview_budget(campaign, actor=customer_user, action="increase_budget", value="300000")
    op = submit_budget_proposal(campaign.pk, actor=customer_user, token=token)
    manager = User.objects.create_user(username="managed-budget-ops", role=User.Role.ADMIN)

    with (
        patch("apps.telegram_ads.services.manage_ad.assert_submission_ready"),
        patch("apps.telegram_ads.services.manage_ad.CampaignPolicyPreflight.operator_submission_allowed", return_value=True),
        patch("apps.telegram_ads.services.manage_ad.require_recorded_approval"),
        patch("apps.finance.account_funding.fund_platform_managed_transfer") as fund,
        patch("apps.telegram_ads.services.manage_ad.campaign_client") as api,
    ):
        fund.return_value = AccountFundingTransfer(
            status=AccountFundingTransfer.Status.COMPLETED,
            amount=Decimal(str(op.request_payload["amount_ton"])),
            currency="TON",
        )
        delta = Decimal(str(op.request_payload["amount_ton"]))
        after = (Decimal("1") + delta).quantize(Decimal("0.01"))
        api.return_value.get_ad.side_effect = [
            {"ad_id": 88, "currency": "TON", "remaining_budget": "1", "status": "active"},
            {"ad_id": 88, "currency": "TON", "remaining_budget": str(after), "status": "active"},
        ]
        api.return_value.increase_ad_budget.return_value = {"ad_id": 88, "remaining_budget": str(after)}
        execute_operation(op.pk, actor=manager)
        fund.assert_called_once()
        api.return_value.increase_ad_budget.assert_called_once()

    wallet = ensure_wallet(customer_user.customer_profile)
    assert outstanding_budget_reservation(wallet, op.pk) == 0
    assert wallet.reserved_irr == 0
    assert WalletLedgerEntry.objects.filter(
        idempotency_key=f"budget-{op.pk}-allocation",
        entry_type=WalletLedgerEntry.EntryType.CREDIT_ALLOCATION,
    ).exists()
    op.refresh_from_db()
    assert op.status == RemoteAdOperation.Status.COMPLETED