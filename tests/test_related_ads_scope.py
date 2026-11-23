from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone
from apps.telegram_ads.models import RelatedAccountRequest, TelegramAdsConnection
from apps.accounts.models import User


@pytest.mark.django_db
def test_child_account_ad_inventory_uses_only_verified_scope(client, customer_user):
    row=RelatedAccountRequest.objects.create(
        customer=customer_user.customer_profile, status="provisioned",
        title="Demo", consent_at=timezone.now(),
        main_account_id="main", remote_account_id="child",
    )
    client.force_login(customer_user)
    with patch("apps.telegram_ads.account_ad_views.verified_client") as verified:
        verified.return_value.get_account_ads_page.return_value = {
            "ads": [{"ad_id":100,"title":"Test","currency":"TON","status":"active"}],
            "next_offset":None,
            "total_count":1,
        }
        url=reverse("accounts:related_ads")
        response=client.get(url+"?load=1")
        assert response.status_code==200
        assert response.context["items"][0]["ad_id"]==100
        verified.return_value.get_account_ads_page.assert_called_once_with(
            account_id="child",offset=None,limit=40,
        )


@pytest.mark.django_db
def test_child_account_inventory_denies_unprovisioned_and_untrusted_cursor(client, customer_user):
    client.force_login(customer_user)
    url=reverse("accounts:related_ads")
    assert client.get(url+"?load=1").status_code==200
    row=RelatedAccountRequest.objects.create(
        customer=customer_user.customer_profile,status="provisioned",
        title="Demo",consent_at=timezone.now(),main_account_id="main",remote_account_id="child",
    )
    with patch("apps.telegram_ads.account_ad_views.verified_client") as verified:
        response=client.get(url+"?load=1&offset="+("a"*600))
        assert "error" in response.context
        verified.assert_not_called()


@pytest.mark.django_db
def test_customer_owned_inventory_uses_only_selected_token(client, customer_user):
    connection = TelegramAdsConnection.objects.create(
        customer=customer_user.customer_profile,
        connection_type="customer_owned", status="connected",
        remote_account_id="personal-64", account_title="Personal account",
        currency="EUR", remaining_budget=10,
        encrypted_access_token="encrypted-not-visible", token_fingerprint="f" * 64,
        is_default=True,
    )
    client.force_login(customer_user)
    with patch("apps.telegram_ads.account_ad_views.connection_client") as make_client:
        make_client.return_value.get_ads_page.return_value = {
            "ads": [{"ad_id": 41, "title": "Existing customer ad", "currency": "EUR", "status": "active"}],
            "next_offset": None, "total_count": 1,
        }
        url = reverse("accounts:related_ads")
        response = client.get(f"{url}?connection_id={connection.pk}&load=1")
        assert response.status_code == 200
        assert response.context["items"][0]["ad_id"] == 41
        assert b"encrypted-not-visible" not in response.content
        make_client.assert_called_once_with(connection)
        make_client.return_value.get_ads_page.assert_called_once_with(offset=None, limit=40)


@pytest.mark.django_db
def test_customer_cannot_load_another_customers_connection(client, customer_user):
    other = User.objects.create_user(
        username="other-ads-user", password="test-password-123", role=User.Role.CUSTOMER,
    )
    connection = TelegramAdsConnection.objects.create(
        customer=other.customer_profile,
        connection_type="customer_owned", status="connected",
        remote_account_id="another-account", currency="EUR", remaining_budget=10,
        encrypted_access_token="other-secret", token_fingerprint="e" * 64,
        is_default=True,
    )
    client.force_login(customer_user)
    with patch("apps.telegram_ads.account_ad_views.connection_client") as make_client:
        response = client.get(reverse("accounts:related_ads") + f"?connection_id={connection.pk}&load=1")
        assert response.status_code == 404
        make_client.assert_not_called()
