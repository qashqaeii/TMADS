"""Public studio regression tests: presentation must not change auth contracts."""
import pytest
from django.urls import reverse
from django.templatetags.static import static
from apps.accounts.forms import RegisterForm


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
    assert [form.fields[name].label for name in ("username", "email", "password1", "password2")] == [
        "نام کاربری", "ایمیل", "رمز عبور", "تکرار رمز عبور"
    ]
    assert form.fields["password1"].widget.input_type == "password"
    assert form.fields["password2"].widget.input_type == "password"
