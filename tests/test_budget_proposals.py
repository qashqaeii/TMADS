from decimal import Decimal
import pytest
from unittest.mock import patch
from apps.campaigns.models import Campaign,TelegramAdvertisement,RemoteAdOperation
from apps.finance.budget_management import preview_budget,submit_budget_proposal
from apps.finance.services import ensure_wallet
from apps.telegram_ads.services.manage_ad import request_operation,execute_operation
from apps.accounts.models import User

@pytest.mark.django_db
def test_decrease_proposal_never_changes_wallet_or_remote(customer_user, settings):
    from apps.telegram_ads.models import TelegramAdsConnection

    campaign = Campaign.objects.create(customer=customer_user.customer_profile, status=Campaign.Status.PAUSED)
    TelegramAdvertisement.objects.create(
        campaign=campaign, remote_ad_id="99",
        remote_status_raw={"currency": "TON", "remaining_budget": 5},
    )
    with patch("apps.telegram_ads.services.manage_ad.campaign_client") as api:
        data, token = preview_budget(campaign, actor=customer_user, action="decrease_budget", value="2.00")
        op = submit_budget_proposal(campaign.pk, actor=customer_user, token=token)
        manager = User.objects.create_user(username="budget-admin", role=User.Role.ADMIN)
        settings.TELEGRAM_ADS_WRITE_ENABLED = settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED = True
        with pytest.raises(ValueError):
            execute_operation(op.pk, actor=manager)
        api.assert_not_called()
    assert op.request_payload["amount_ton"] == "2.00"
    assert ensure_wallet(campaign.customer).reserved_irr == 0
    assert RemoteAdOperation.objects.count() == 1
    with pytest.raises(ValueError):
        request_operation(campaign.pk, actor=customer_user, action="increase_budget", value="5")

    connection = TelegramAdsConnection.objects.create(
        customer=customer_user.customer_profile,
        connection_type=TelegramAdsConnection.Type.CUSTOMER_OWNED,
        status=TelegramAdsConnection.Status.CONNECTED,
        remote_account_id="byoa-budget",
        currency="TON",
        remaining_budget=Decimal("10"),
        encrypted_access_token="enc",
        token_fingerprint="c" * 64,
        is_default=True,
    )
    owned = Campaign.objects.create(
        customer=customer_user.customer_profile,
        telegram_connection=connection,
        status=Campaign.Status.PAUSED,
    )
    TelegramAdvertisement.objects.create(
        campaign=owned, remote_ad_id="101",
        remote_status_raw={"currency": "TON", "remaining_budget": "5"},
    )
    data, token = preview_budget(owned, actor=customer_user, action="decrease_budget", value="2.00")
    op2 = submit_budget_proposal(owned.pk, actor=customer_user, token=token)
    with patch("apps.telegram_ads.services.manage_ad.assert_submission_ready"), patch(
        "apps.telegram_ads.services.manage_ad.campaign_client"
    ) as api:
        api.return_value.get_ad.side_effect = [
            {"ad_id": 101, "currency": "TON", "remaining_budget": "5", "status": "on_hold"},
            {"ad_id": 101, "currency": "TON", "remaining_budget": "3", "status": "on_hold"},
        ]
        api.return_value.decrease_ad_budget.return_value = {"ad_id": 101, "remaining_budget": "3"}
        execute_operation(op2.pk, actor=manager)
        api.return_value.decrease_ad_budget.assert_called_once()
    op2.refresh_from_db()
    assert op2.status == "completed"
