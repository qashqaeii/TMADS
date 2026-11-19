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
