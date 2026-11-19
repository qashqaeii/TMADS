"""No live upload, correct account-bound receipt and strict image contract."""
from io import BytesIO
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.campaigns.models import Campaign, AdCreative
from apps.campaigns.media_validation import validate_website_photo
from apps.telegram_ads.services.website_photo import website_photo_receipt, upload_saved_website_photo
from apps.telegram_ads.exceptions import TelegramAdsError


def photo(format="PNG", size=(150,150)):
    buf = BytesIO()
    Image.new("RGB", size).save(buf, format=format)
    buf.seek(0)
    return SimpleUploadedFile("site.png", buf.getvalue(), content_type="image/png")


def test_website_photo_validation():
    assert not validate_website_photo(photo())
    assert validate_website_photo(photo(size=(149,150)))
    assert validate_website_photo(SimpleUploadedFile("x.webp", b"not-valid", content_type="image/webp"))


@pytest.mark.django_db
def test_website_upload_is_off_by_default_and_creates_no_api_calls(customer_user, settings):
    settings.TELEGRAM_ADS_WRITE_ENABLED = False
    campaign = Campaign.objects.create(customer=customer_user.customer_profile,
        destination="https://example.com", name="Site",
        ad_settings={"destination_rights_confirmed":True})
    AdCreative.objects.create(campaign=campaign, website_photo=photo())
    with patch("apps.telegram_ads.services.website_photo.TelegramAdsClient") as api:
        with pytest.raises(ValueError):
            upload_saved_website_photo(campaign, actor=customer_user)
        api.assert_not_called()
    assert website_photo_receipt(campaign) is None
