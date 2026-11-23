from unittest.mock import patch
from decimal import Decimal

import pytest
from apps.campaigns.models import Campaign, CampaignTargeting
from apps.campaigns.views import _create_quote
from apps.finance.models import AdvertisingOrder
from apps.finance.services import credit_wallet_deposit, ensure_wallet, reserve_for_order
from apps.telegram_ads.services.submission import submit_campaign_to_telegram
from apps.telegram_ads.services.ad_payload import build_create_ad_payload
from apps.telegram_ads.exceptions import TelegramAdsError


def paid_campaign(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile, target_type="search", placement="search_result",
        destination="https://t.me/test", name="paid", budget_irr=2_000_000, ad_settings={"terms_accepted": True},
    )
    CampaignTargeting.objects.create(campaign=campaign, config={"search_queries": ["test"]})
    _create_quote(campaign)
    order = AdvertisingOrder.objects.get(campaign_id=campaign.id)
    wallet = ensure_wallet(campaign.customer)
    credit_wallet_deposit(wallet, order.total_irr, "test-deposit")
    reserve_for_order(wallet, order.total_irr, order.id, f"reserve-{order.id}")
    order.status = AdvertisingOrder.Status.PAID
    order.save(update_fields=["status"])
    campaign.status = Campaign.Status.READY_FOR_SUBMISSION
    campaign.save(update_fields=["status"])
    from apps.policies.services.preflight import CampaignPolicyPreflight
    from apps.policies.services.policy_versions import get_active_policy_version
    from apps.policies.models import OpsPolicyReview
    CampaignPolicyPreflight.record_acceptance(campaign)
    OpsPolicyReview.objects.create(campaign=campaign, reviewer=customer_user, decision="approve",
        reason_customer_fa="test fixture", policy_version_code=get_active_policy_version().code)
    return campaign, order


@pytest.mark.django_db
def test_paid_payload_uses_locked_amount(customer_user):
    campaign, order = paid_campaign(customer_user)
    with patch("apps.telegram_ads.services.ad_payload.ton_allocation_for_budget", side_effect=AssertionError("no recalculation")):
        payload = build_create_ad_payload(campaign, order=order)
    assert Decimal(str(payload["initial_budget"])) == order.ton_allocation
    assert payload["idempotency_key"] == f"tmads-create-{campaign.id}"


@pytest.mark.django_db
def test_uncertain_create_cannot_be_retried(customer_user, settings):
    settings.TELEGRAM_ADS_WRITE_ENABLED = settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED = True
    campaign, order = paid_campaign(customer_user)
    with patch("apps.policies.services.preflight.assert_submission_ready"), patch("apps.telegram_ads.services.submission.campaign_client") as account, patch("apps.telegram_ads.services.submission.TelegramAdsClient") as central, patch("apps.telegram_ads.services.submission.execute_create_ad", side_effect=TimeoutError) as execute:
        account.return_value.get_account.return_value = {"currency": "TON", "remaining_budget": 500}
        central.return_value.get_account.return_value = {"currency": "TON", "remaining_budget": 500, "account_id": "main-1"}
        with pytest.raises(TelegramAdsError):
            submit_campaign_to_telegram(campaign)
        with pytest.raises(ValueError):
            submit_campaign_to_telegram(campaign)
        execute.assert_called_once()
    campaign.refresh_from_db()
    assert campaign.status == Campaign.Status.RECONCILIATION
