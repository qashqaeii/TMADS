from unittest.mock import patch
import pytest
from apps.campaigns.intraday_views import normalize_rows
from apps.telegram_ads.models import RelatedAccountRequest
from apps.telegram_ads.services.customer_assets import create_asset,issue_nonce,verified_client
from django.utils import timezone

def test_missing_metrics_are_not_zero():
    rows=normalize_rows([{"from_time":300,"to_time":600,"views":0,"currency":"TON","spent_budget":"1.25"}],300,600)
    assert rows[0]["views"]==0
    assert rows[0]["clicks"] is None

def test_duplicate_period_is_rejected():
    row={"from_time":300,"to_time":600}
    with pytest.raises(ValueError):
        normalize_rows([row,row],300,600)

@pytest.mark.django_db
def test_asset_gate_and_account_identity(customer_user,settings):
    row=RelatedAccountRequest.objects.create(customer=customer_user.customer_profile,status="provisioned",
        title="Test",consent_at=timezone.now(),main_account_id="main",remote_account_id="child")
    settings.TELEGRAM_ADS_CUSTOMER_ASSETS_ENABLED=False
    with patch("apps.telegram_ads.services.customer_assets.TelegramAdsClient") as api:
        with pytest.raises(ValueError):
            create_asset(customer_user,{"action":"pixel","consent":"on","nonce":issue_nonce(row)})
        api.assert_not_called()
        api.return_value.get_account.return_value={"account_id":"different"}
        with pytest.raises(ValueError):
            verified_client(row)
        api.return_value.get_account_info.assert_not_called()
