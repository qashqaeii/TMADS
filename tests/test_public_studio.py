"""Public studio regression tests: presentation must not change auth contracts."""
import pytest
from django.urls import reverse
from django.templatetags.static import static
from apps.accounts.forms import RegisterForm
from apps.accounts.models import User


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["public:home", "public:features", "accounts:login", "accounts:register"])
def test_studio_assets(client, route):
    response = client.get(reverse(route))
    assert response.status_code == 200
    assert static("css/public-studio.css") in response.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["accounts:login", "accounts:register"])
def test_auth_has_dedicated_shell(client, route):
    html = client.get(reverse(route)).content.decode()
    assert 'class="studio-auth-header"' in html
    assert 'class="ao-art"' in html
    assert 'class="studio-auth-footer container"' in html
    assert 'csrfmiddlewaretoken' in html
    assert 'class="site-header site-header--exec' not in html


def test_registration_labels_and_password_widgets():
    form = RegisterForm()
    assert [form.fields[name].label for name in ("username", "mobile", "password1", "password2")] == [
        "نام کاربری", "شماره تماس", "رمز عبور", "تکرار رمز عبور"
    ]
    assert form.fields["password1"].widget.input_type == "password"
    assert form.fields["password2"].widget.input_type == "password"
    assert "email" not in form.fields


@pytest.mark.django_db
def test_registration_accepts_freeform_username_over_five_chars():
    form = RegisterForm(
        data={
            "username": "حسین کشکولی",
            "mobile": "09123456789",
            "password1": "S3cure-test-password!",
            "password2": "S3cure-test-password!",
        }
    )
    assert form.is_valid(), form.errors
    assert form.cleaned_data["username"] == "حسین کشکولی"
    assert form.cleaned_data["mobile"] == "09123456789"


@pytest.mark.django_db
def test_registration_rejects_username_five_or_fewer_chars():
    form = RegisterForm(
        data={
            "username": "حسینک",
            "mobile": "09123456789",
            "password1": "S3cure-test-password!",
            "password2": "S3cure-test-password!",
        }
    )
    assert not form.is_valid()
    assert "username" in form.errors


@pytest.mark.django_db
def test_registration_requires_valid_unique_mobile():
    User.objects.create_user(username="existing_user", password="S3cure-test-password!", mobile="09121111111")
    invalid = RegisterForm(
        data={
            "username": "کاربر جدید",
            "mobile": "12345",
            "password1": "S3cure-test-password!",
            "password2": "S3cure-test-password!",
        }
    )
    assert not invalid.is_valid()
    assert "mobile" in invalid.errors

    duplicate = RegisterForm(
        data={
            "username": "کاربر دیگر",
            "mobile": "+98 912 111 1111",
            "password1": "S3cure-test-password!",
            "password2": "S3cure-test-password!",
        }
    )
    assert not duplicate.is_valid()
    assert "mobile" in duplicate.errors

    ok = RegisterForm(
        data={
            "username": "کاربر موفق",
            "mobile": "۰۹۱۲۳۴۵۶۷۸۹",
            "password1": "S3cure-test-password!",
            "password2": "S3cure-test-password!",
        }
    )
    assert ok.is_valid(), ok.errors
    user = ok.save()
    assert user.mobile == "09123456789"
    assert user.email == ""
