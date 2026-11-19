"""No phone numbers in persistence; exact identity and opt-in gates."""
from unittest.mock import patch

import pytest
from django.utils import timezone
from apps.telegram_ads.models import RelatedAccountRequest, AccountAssetOperation
from apps.telegram_ads.services.customer_assets import _sha256_list, change_audience_contacts


def test_only_sha256_values_are_accepted():
    assert _sha256_list(("a"*64+"\n"+"b"*64)) == ["a"*64,"b"*64]
    for value in ["+989123456789", "0123456789", "a"*64+"\n"+"a"*64, "x"*64]:
        with pytest.raises(ValueError):
            _sha256_list(value)


@pytest.mark.django_db
def test_no_contact_upload_when_gated(customer_user, settings):
    row=RelatedAccountRequest.objects.create(customer=customer_user.customer_profile,
        status="provisioned", title="Example", consent_at=timezone.now(),
        main_account_id="main", remote_account_id="child")
    settings.TELEGRAM_ADS_CUSTOMER_ASSETS_ENABLED = False
    with patch("apps.telegram_ads.services.customer_assets.TelegramAdsClient") as api:
        with pytest.raises(ValueError):
            change_audience_contacts(customer_user, {
                "action":"add", "audience_id":"1", "sha256_list":"a"*64,
                "consent":"on", "data_rights":"on",
            })
        api.assert_not_called()


@pytest.mark.django_db
def test_successful_audience_edit_persists_only_metadata(customer_user):
    from apps.telegram_ads.services.customer_assets import issue_nonce
    row=RelatedAccountRequest.objects.create(customer=customer_user.customer_profile,
        status="provisioned", title="Example", consent_at=timezone.now(),
        main_account_id="main", remote_account_id="child")
    secret_hash="a"*64
    with patch("apps.telegram_ads.services.customer_assets.enabled", return_value=True), patch(
        "apps.telegram_ads.services.customer_assets.verified_client"
    ) as verified:
        verified.return_value.get_audiences_by_ids.return_value=[{"audience_id":17}]
        verified.return_value.edit_audience_hashes.return_value={"audience_id":17}
        op=change_audience_contacts(customer_user,{
            "action":"add","audience_id":"17","sha256_list":secret_hash,
            "consent":"on","data_rights":"on","nonce":issue_nonce(row),
        })
        assert op.state == "executing" or op.state == "completed"
        op.refresh_from_db()
        assert op.state == "completed"
        assert secret_hash not in str(op.__dict__)
        verified.return_value.edit_audience_hashes.assert_called_once()



@pytest.mark.django_db
def test_audience_delete_requires_explicit_zero_ads_count(customer_user):
    from apps.telegram_ads.services.customer_assets import delete_unused_audience, issue_nonce
    row=RelatedAccountRequest.objects.create(customer=customer_user.customer_profile,
        status="provisioned", title="Example", consent_at=timezone.now(),
        main_account_id="main", remote_account_id="child")
    with patch("apps.telegram_ads.services.customer_assets.enabled", return_value=True), patch(
        "apps.telegram_ads.services.customer_assets.verified_client"
    ) as verified:
        for record in [{"audience_id":42}, {"audience_id":42,"ads_count":1}]:
            verified.return_value.get_audiences_by_ids.return_value=[record]
            with pytest.raises(ValueError):
                delete_unused_audience(customer_user, {
                    "audience_id":"42", "nonce":issue_nonce(row), "consent":"on",
                })
        verified.return_value.delete_unused_audience.assert_not_called()
        verified.return_value.get_audiences_by_ids.return_value=[{"audience_id":42,"ads_count":0}]
        verified.return_value.delete_unused_audience.return_value=True
        result=delete_unused_audience(customer_user, {
            "audience_id":"42", "nonce":issue_nonce(row), "consent":"on",
        })
        result.refresh_from_db()
        assert result.state=="completed"
        verified.return_value.delete_unused_audience.assert_called_once()



@pytest.mark.django_db
def test_pixel_event_is_not_deleted_if_unknown_or_used(customer_user):
    from apps.telegram_ads.services.customer_assets import manage_pixel_event, issue_nonce
    row=RelatedAccountRequest.objects.create(customer=customer_user.customer_profile,
        status="provisioned", title="Example", consent_at=timezone.now(),
        main_account_id="main", remote_account_id="child")
    with patch("apps.telegram_ads.services.customer_assets.enabled", return_value=True), patch(
        "apps.telegram_ads.services.customer_assets.verified_client"
    ) as verified:
        for value in [
            {"event_id":"ev1","auto_created":True,"ads_count":0},
            {"event_id":"ev1","auto_created":False},
            {"event_id":"ev1","auto_created":False,"ads_count":2},
        ]:
            verified.return_value.get_pixel_events_by_ids.return_value=[value]
            with pytest.raises(ValueError):
                manage_pixel_event(customer_user,{
                    "event_id":"ev1","action":"delete","nonce":issue_nonce(row),"consent":"on",
                })
        verified.return_value.change_pixel_event.assert_not_called()
        verified.return_value.get_pixel_events_by_ids.return_value=[{
            "event_id":"ev1","auto_created":False,"ads_count":0,
        }]
        verified.return_value.change_pixel_event.return_value=True
        op=manage_pixel_event(customer_user,{
            "event_id":"ev1","action":"delete","nonce":issue_nonce(row),"consent":"on",
        })
        op.refresh_from_db()
        assert op.state=="completed"
        verified.return_value.change_pixel_event.assert_called_once()
