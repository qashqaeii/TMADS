from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse

from apps.accounts.models import User
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsNotConfigured
from apps.telegram_ads.models import TelegramAdsConnection, TelegramAdsPlatformCredential
from apps.telegram_ads.services.platform_credentials import (
    active_platform_token, configure_platform_token,
)


@pytest.fixture
def manager(db):
    return User.objects.create_user(username="platform-manager-test", role=User.Role.ADMIN)


def provider_mock():
    from unittest.mock import MagicMock
    api = MagicMock()
    api.get_account.return_value = {
        "account_id": "central-100", "title": "Central", "currency": "TON",
        "remaining_budget": "14.5",
    }
    api.get_account_info.return_value = {"account_id": "central-100", "title": "Central"}
    return api


@pytest.mark.django_db
def test_central_token_is_encrypted_and_preferred_over_legacy_env(manager, settings):
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-unit-test-secret-" * 4
    settings.TELEGRAM_ADS_API_TOKEN = "legacy-token"
    with patch("apps.telegram_ads.services.platform_credentials.TelegramAdsClient") as make_client:
        make_client.return_value = provider_mock()
        credential = configure_platform_token(manager, "private-central-token")
    credential.refresh_from_db()
    assert credential.remote_account_id == "central-100"
    assert "private-central-token" not in credential.encrypted_access_token
    assert active_platform_token() == "private-central-token"
    api = TelegramAdsClient()
    api._ensure_configured()
    assert api.token == "private-central-token"


@pytest.mark.django_db
def test_central_token_can_only_rotate_on_same_account(manager, settings):
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-unit-test-secret-" * 4
    with patch("apps.telegram_ads.services.platform_credentials.TelegramAdsClient") as make_client:
        make_client.return_value = provider_mock()
        one = configure_platform_token(manager, "first")
        two = configure_platform_token(manager, "second")
    assert one.pk == two.pk
    assert TelegramAdsPlatformCredential.objects.count() == 1
    assert active_platform_token() == "second"


@pytest.mark.django_db
def test_corrupt_database_key_never_falls_back_to_env(manager, settings):
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-unit-test-secret-" * 4
    with patch("apps.telegram_ads.services.platform_credentials.TelegramAdsClient") as make_client:
        make_client.return_value = provider_mock()
        configure_platform_token(manager, "private")
    settings.TELEGRAM_ADS_API_TOKEN = "legacy-fallback-must-not-run"
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "another-high-entropy-encryption-key"
    with pytest.raises(TelegramAdsNotConfigured):
        active_platform_token()


@pytest.mark.django_db
def test_customer_cannot_register_or_read_platform_token(client, customer_user, settings):
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-unit-test-secret-" * 4
    client.force_login(customer_user)
    url = reverse("operations:platform_api_token")
    assert client.get(url).status_code == 403
    with patch("apps.telegram_ads.services.platform_credentials.TelegramAdsClient") as make_client:
        assert client.post(url, {"api_token": "unauthorized"}).status_code == 403
        make_client.assert_not_called()
    with pytest.raises(PermissionDenied):
        configure_platform_token(customer_user, "unauthorized")


@pytest.mark.django_db
def test_manager_credential_form_never_echoes_token(client, manager, settings):
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-unit-test-secret-" * 4
    client.force_login(manager)
    with patch("apps.telegram_ads.services.platform_credentials.TelegramAdsClient") as make_client:
        make_client.return_value = provider_mock()
        response = client.post(
            reverse("operations:platform_api_token"),
            {"api_token": "do-not-ever-display"}, follow=True,
        )
    assert response.status_code == 200
    assert "do-not-ever-display" not in response.content.decode()
    assert TelegramAdsPlatformCredential.objects.count() == 1


@pytest.mark.django_db
def test_customer_cannot_connect_platform_account(manager, customer_user, settings):
    from apps.telegram_ads.services.account_connections import connect_customer_owned_account
    settings.TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = "high-entropy-unit-test-secret-" * 4
    settings.TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED = True
    with patch("apps.telegram_ads.services.platform_credentials.TelegramAdsClient") as make_client:
        make_client.return_value = provider_mock()
        configure_platform_token(manager, "admin-token")
    with patch("apps.telegram_ads.services.account_connections.TelegramAdsClient") as make_client:
        make_client.return_value = provider_mock()
        with pytest.raises(ValueError, match="مرکزی"):
            connect_customer_owned_account(customer_user, "attempt-to-bind-central")
    assert not TelegramAdsConnection.objects.filter(customer=customer_user.customer_profile).exists()
