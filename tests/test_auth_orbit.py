"""Orbit Access preserves Django authentication and scopes cosmetic assets."""
from urllib.parse import urlencode

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize("route, fields, art", [
    ("accounts:login", ("username", "password"), "img/features/telegram_glassmorphism_analytics_hero.webp"),
    ("accounts:register", ("username", "mobile", "password1", "password2"), "img/workflow/tmads_workflow_hero.webp"),
])
def test_auth_orbit_shell(client, route, fields, art):
    response = client.get(reverse(route))
    assert response.status_code == 200
    html = response.content.decode()
    assert "orbit-auth" in html and html.count("<h1") == 1
    assert static("css/auth-orbit.css") in html
    assert static("js/auth-orbit.js") in html
    assert static(art) in html
    assert finders.find(art)
    assert 'csrfmiddlewaretoken' in html
    for field in fields:
        assert f'name="{field}"' in html
        assert f'for="id_{field}"' in html
    assert reverse("accounts:login") in html
    assert reverse("accounts:register") in html
    for other in ("public:home", "public:contact", "accounts:password_reset"):
        page = client.get(reverse(other)).content.decode()
        assert static("css/auth-orbit.css") not in page
        assert static("js/auth-orbit.js") not in page


@pytest.mark.django_db
@pytest.mark.parametrize("next_url, allowed", [
    ("/support/new/", True),
    ("https://example.invalid/", False),
    ("//example.invalid/", False),
    ("/\\example.invalid/", False),
    ("", False),
])
def test_login_next_only_safe_local_paths(client, customer_user, next_url, allowed):
    response = client.post(
        reverse("accounts:login") + "?" + urlencode({"next": next_url}),
        {"username": customer_user.username, "password": "pass1234"},
    )
    assert response.status_code == 302
    assert response.url == (next_url if allowed else reverse("dashboard:home"))


@pytest.mark.django_db
def test_auth_validation_keeps_errors_and_masks_passwords(client):
    response = client.post(reverse("accounts:login"), {"username": "missing", "password": "test-only-invalid"})
    assert response.status_code == 200
    assert b'role="alert"' in response.content
    assert b'test-only-invalid' not in response.content
    response = client.post(reverse("accounts:register"), {
        "username": "orbit_new_user", "mobile": "not-a-phone",
        "password1": "Distinct-test-value-234!", "password2": "different",
    })
    assert response.status_code == 200
    assert b'role="alert"' in response.content
    assert b'Distinct-test-value-234!' not in response.content
    assert b'name="email"' not in response.content
