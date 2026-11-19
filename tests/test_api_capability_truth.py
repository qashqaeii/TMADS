from unittest.mock import patch

import pytest
from apps.telegram_ads.services.capabilities import refresh_api_capabilities
from apps.telegram_ads.models import APICapability
from apps.telegram_ads.exceptions import TelegramAdsApiError, TelegramAdsTransportError


@pytest.mark.django_db
def test_capability_matrix_does_not_infer_permission_denial_from_network(settings):
    settings.TELEGRAM_ADS_WRITE_ENABLED = False
    with patch("apps.telegram_ads.services.capabilities._probe_read",
            side_effect=TelegramAdsTransportError("offline")):
        assert refresh_api_capabilities() > 0
    assert APICapability.objects.get(feature_key="ads.list").state == APICapability.State.TEMPORARY
    cap = APICapability.objects.get(feature_key="ads.create")
    assert cap.state == APICapability.State.UNVERIFIED
    assert cap.details["reason"] == "write_disabled_by_tmads_not_api_capability"


@pytest.mark.django_db
def test_capability_matrix_distinguishes_targeting_error_from_permission_denial():
    with patch("apps.telegram_ads.services.capabilities._probe_read",
            side_effect=TelegramAdsApiError("BOT_TOO_SMALL", method="getTargetBot")):
        refresh_api_capabilities()
    assert APICapability.objects.get(feature_key="targeting.bot").state == APICapability.State.UNVERIFIED
    with patch("apps.telegram_ads.services.capabilities._probe_read",
            side_effect=TelegramAdsApiError("ACCESS_DENIED", method="getPixel")):
        refresh_api_capabilities()
    assert APICapability.objects.get(feature_key="pixel.read").state == APICapability.State.PERMISSION_DENIED
