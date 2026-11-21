from unittest.mock import patch

import pytest

from apps.campaigns.models import Campaign, TelegramAdvertisement
from apps.finance.models import AdvertisingOrder, Wallet
from apps.telegram_ads.models import TelegramAdsConnection
from apps.telegram_ads.services.submission import submit_campaign_to_telegram


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
    )

    def claim(campaign_id):
        Campaign.objects.filter(pk=campaign_id).update(status=Campaign.Status.SUBMITTING)
        return Campaign.objects.get(pk=campaign_id)

    def create_remote_ad(current, *, mode):
        return TelegramAdvertisement.objects.create(
            campaign=current,
            remote_ad_id="987654321",
            remote_status="ready_for_review",
        )

    with (
        patch("apps.telegram_ads.services.submission._claim_customer_owned_submission", side_effect=claim),
        patch("apps.telegram_ads.services.submission.execute_create_ad", side_effect=create_remote_ad),
    ):
        result = submit_campaign_to_telegram(campaign)

    assert result.remote_ad_id == "987654321"
    assert not AdvertisingOrder.objects.filter(campaign=campaign).exists()
    assert not Wallet.objects.filter(customer=customer_user.customer_profile).exists()
