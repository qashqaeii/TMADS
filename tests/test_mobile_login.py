"""Regression tests for password login with existing username/mobile identifiers."""
import pytest
from django.urls import reverse

from apps.accounts.models import User


PHONE = "09120000000"
PASSWORD = "Local-test-only-123!"


@pytest.fixture
def mobile_user():
    return User.objects.create_user(
        username="orbit_mobile_customer", mobile=PHONE, password=PASSWORD,
    )


def sign_in(client, identifier, password=PASSWORD):
    return client.post(reverse("accounts:login"), {
        "username": identifier, "password": password,
    })


@pytest.mark.parametrize("identifier", [
    "orbit_mobile_customer",
    PHONE,
    "۰۹۱۲۰۰۰۰۰۰۰",
    "٠٩١٢٠٠٠٠٠٠٠",
    "+989120000000",
    "00989120000000",
    "989120000000",
    "0912 000 0000",
    " 0912-000-0000 ",
])
def test_login_by_username_or_mobile(client, mobile_user, identifier):
    response = sign_in(client, identifier)
    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    assert client.session["_auth_user_id"] == str(mobile_user.pk)


def test_legacy_mobile_format(client, mobile_user):
    mobile_user.mobile = "+989120000000"
    mobile_user.save(update_fields=["mobile"])
    assert sign_in(client, PHONE).status_code == 302
    assert client.session["_auth_user_id"] == str(mobile_user.pk)


def test_wrong_password_and_unknown_mobile_have_same_error(client, mobile_user):
    for identifier in (PHONE, "09129999999"):
        response = sign_in(client, identifier, "wrong-password")
        assert response.status_code == 200
        assert "نام کاربری یا شماره موبایل یا رمز عبور اشتباه است." in response.content.decode()
        assert "_auth_user_id" not in client.session


def test_duplicate_mobile_rejected_but_username_still_works(client, mobile_user):
    User.objects.create_user(username="other_mobile_customer", mobile=PHONE, password=PASSWORD)
    assert sign_in(client, PHONE).status_code == 200
    assert "_auth_user_id" not in client.session
    assert sign_in(client, mobile_user.username).status_code == 302
    assert client.session["_auth_user_id"] == str(mobile_user.pk)


def test_exact_numeric_username_takes_priority(client, mobile_user):
    legacy = User.objects.create_user(username=PHONE, password=PASSWORD)
    assert sign_in(client, PHONE).status_code == 302
    assert client.session["_auth_user_id"] == str(legacy.pk)


def test_numeric_username_with_persian_digits(client):
    user = User.objects.create_user(username=PHONE, password=PASSWORD)
    assert sign_in(client, "۰۹۱۲۰۰۰۰۰۰۰").status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


def test_disabled_account_cannot_sign_in_by_mobile(client, mobile_user):
    mobile_user.is_active = False
    mobile_user.save(update_fields=["is_active"])
    response = sign_in(client, PHONE)
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


def test_mobile_login_requires_password(client, mobile_user):
    response = sign_in(client, PHONE, "")
    assert response.status_code == 200
    assert "رمز عبور را وارد کنید." in response.content.decode()
    assert "_auth_user_id" not in client.session
