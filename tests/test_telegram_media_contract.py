from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.campaigns.media_validation import validate_telegram_creative_media
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsWriteDisabled
from unittest.mock import patch
import pytest

@pytest.mark.parametrize("size,valid", [((640,360),True),((32,32),False),((640,400),False)])
def test_photo_dimensions(size,valid):
    buf=BytesIO()
    Image.new("RGB",size).save(buf,format="PNG")
    assert (not validate_telegram_creative_media(SimpleUploadedFile("image.png",buf.getvalue()))) == valid

def test_upload_disabled_does_not_contact_telegram(settings):
    settings.TELEGRAM_ADS_MEDIA_UPLOAD_ENABLED=False
    with patch.object(TelegramAdsClient,"_run") as run:
        with pytest.raises(TelegramAdsWriteDisabled):
            TelegramAdsClient().upload_creative_media(BytesIO(b"content"),filename="creative.png",is_video=False)
        run.assert_not_called()



@pytest.mark.django_db
def test_uncertain_media_upload_blocks_second_write(customer_user, settings, tmp_path):
    from apps.campaigns.models import Campaign, AdCreative
    from apps.telegram_ads.models import APIRequestLog
    from apps.telegram_ads.services.media import upload_saved_media
    settings.MEDIA_ROOT = str(tmp_path)
    settings.TELEGRAM_ADS_API_TOKEN = "isolated-test-token"
    buf = BytesIO()
    Image.new("RGB", (640, 360)).save(buf, format="PNG")
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile, name="Media",
        target_type="channels", destination="https://t.me/example",
        ad_settings={"destination_rights_confirmed": True},
    )
    AdCreative.objects.create(campaign=campaign, media=SimpleUploadedFile("test.png", buf.getvalue()))
    with patch("apps.telegram_ads.services.media.media_upload_enabled", return_value=True), patch(
        "apps.telegram_ads.services.media.TelegramAdsClient"
    ) as api:
        api.return_value.upload_creative_media.side_effect = TimeoutError("simulated")
        with pytest.raises(ValueError):
            upload_saved_media(campaign, actor=customer_user)
        assert APIRequestLog.objects.filter(
            operation="media_upload_claim", meta__state="uncertain",
        ).exists()
        with pytest.raises(ValueError):
            upload_saved_media(campaign, actor=customer_user)
        api.return_value.upload_creative_media.assert_called_once()
