from io import BytesIO
from PIL import Image
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from apps.accounts.models import User
from apps.campaigns.models import Campaign, AdCreative
from apps.campaigns.media_validation import validate_ad_image, validate_ad_video
from apps.telegram_ads.targeting.validators import validate_submission_ready


def test_truncated_image_and_wrong_extension_are_rejected():
    buffer = BytesIO()
    Image.new("RGB", (32, 32)).save(buffer, format="PNG")
    raw = buffer.getvalue()
    assert not validate_ad_image(SimpleUploadedFile("good.png", raw))
    assert validate_ad_image(SimpleUploadedFile("broken.png", raw[:20]))
    assert validate_ad_image(SimpleUploadedFile("fake.jpg", raw))


def test_video_rejects_extension_only():
    assert validate_ad_video(SimpleUploadedFile("fake.mp4", b"not a video"))


@pytest.mark.django_db
def test_media_download_is_private_and_unuploaded_media_blocks_payment(client, customer_user, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, name="Media",
        target_type="channels", placement="channel_post", budget_irr=1000000, destination="https://t.me/test")
    creative = AdCreative.objects.create(campaign=campaign, media=SimpleUploadedFile("asset.png", b"test"))
    assert any("رسانه" in error for error in validate_submission_ready(campaign).errors)
    url = reverse("campaigns:creative_media", args=[campaign.pk, creative.pk])
    other = User.objects.create_user(username="media-other", password="pass1234", role=User.Role.CUSTOMER)
    client.force_login(other)
    assert client.get(url).status_code == 404
    client.force_login(customer_user)
    response = client.get(url)
    assert response.status_code == 200 and response["Cache-Control"] == "private, no-store"
    response.close()
