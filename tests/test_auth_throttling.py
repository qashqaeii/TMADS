"""Fixed-window authentication throttling: shared IPs and brute-force attempts."""
import pytest
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from apps.accounts.models import User


@pytest.mark.django_db
@override_settings(DEBUG=False, APP_ENV="PRODUCTION")
def test_login_failed_attempts_throttled_per_identifier(client):
    cache.clear()
    try:
        url = reverse("accounts:login")
        for _ in range(10):
            assert client.post(url, {"username": "target-user", "password": "wrong"}).status_code == 200
        denied = client.post(url, {"username": "target-user", "password": "wrong"})
        assert denied.status_code == 429
        assert denied["Retry-After"] == "300"
        # A different account behind the same office/public IP remains usable.
        user = User.objects.create_user(username="office-colleague", password="S3cure-test-password!")
        ok = client.post(url, {"username": user.username, "password": "S3cure-test-password!"})
        assert ok.status_code == 302
    finally:
        cache.clear()


@pytest.mark.django_db
@override_settings(DEBUG=False, APP_ENV="PRODUCTION")
def test_successful_logins_do_not_consume_failed_attempt_quota(client):
    cache.clear()
    try:
        user = User.objects.create_user(username="regular-user", password="S3cure-test-password!")
        url = reverse("accounts:login")
        for _ in range(12):
            ok = client.post(url, {"username": user.username, "password": "S3cure-test-password!"})
            assert ok.status_code == 302
            client.logout()
        assert client.post(url, {"username": user.username, "password": "wrong"}).status_code == 200
    finally:
        cache.clear()


@pytest.mark.django_db
@override_settings(DEBUG=False, APP_ENV="PRODUCTION")
def test_register_rate_limit_is_per_ip_and_stops_repetition(client):
    cache.clear()
    try:
        url = reverse("accounts:register")
        for _ in range(20):
            assert client.post(url, {}).status_code == 200
        blocked = client.post(url, {})
        assert blocked.status_code == 429
    finally:
        cache.clear()
