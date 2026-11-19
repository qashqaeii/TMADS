from unittest.mock import patch
import pytest
from django.urls import reverse
from apps.accounts.models import User
from apps.campaigns.models import Campaign, TelegramAdvertisement, RemoteAdOperation
from apps.telegram_ads.services.manage_ad import request_operation, execute_operation, parse_request
from apps.telegram_ads.exceptions import TelegramAdsError


def setup_ad(customer_user):
    campaign=Campaign.objects.create(customer=customer_user.customer_profile,status=Campaign.Status.ACTIVE)
    ad=TelegramAdvertisement.objects.create(campaign=campaign,remote_ad_id="101",remote_status="active")
    return campaign,ad


@pytest.mark.django_db
def test_duplicate_requests_and_disabled_write(customer_user,settings):
    settings.TELEGRAM_ADS_WRITE_ENABLED=False
    campaign,ad=setup_ad(customer_user)
    op=request_operation(campaign.pk,actor=customer_user,action="pause")
    with pytest.raises(ValueError):
        request_operation(campaign.pk,actor=customer_user,action="pause")
    manager=User.objects.create_user(username="ops-remote",role=User.Role.ADMIN)
    with patch("apps.telegram_ads.services.manage_ad.TelegramAdsClient") as api:
        with pytest.raises(ValueError):
            execute_operation(op.pk,actor=manager)
        api.assert_not_called()
    op.refresh_from_db()
    assert op.status=="pending"


@pytest.mark.django_db
def test_pause_uncertainty_blocks_retry(customer_user,settings):
    settings.TELEGRAM_ADS_WRITE_ENABLED=settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED=True
    campaign,ad=setup_ad(customer_user)
    op=request_operation(campaign.pk,actor=customer_user,action="pause")
    manager=User.objects.create_user(username="ops-remote",role=User.Role.ADMIN)
    with patch("apps.telegram_ads.services.manage_ad.CampaignPolicyPreflight.operator_submission_allowed",return_value=True), patch("apps.telegram_ads.services.manage_ad.TelegramAdsClient") as api:
        api.return_value.get_ad.return_value={"ad_id":101,"status":"active","currency":"TON"}
        api.return_value.edit_advertisement.side_effect=TimeoutError
        with pytest.raises(TelegramAdsError):
            execute_operation(op.pk,actor=manager)
        with pytest.raises(ValueError):
            execute_operation(op.pk,actor=manager)
        api.return_value.edit_advertisement.assert_called_once()
    op.refresh_from_db()
    assert op.status=="uncertain"


@pytest.mark.django_db
def test_customer_cannot_open_other_customer_ad(client,customer_user):
    other=User.objects.create_user(username="other-remote",role=User.Role.CUSTOMER)
    campaign,ad=setup_ad(other)
    client.force_login(customer_user)
    assert client.get(reverse("campaigns:remote_management",args=[campaign.pk])).status_code==404
    assert client.get(reverse("operations:remote_operations")).status_code==403


@pytest.mark.parametrize("value",["NaN","-1","0.001","Infinity"])
def test_invalid_cpm(value):
    with pytest.raises(ValueError):
        parse_request("edit_cpm",value)
