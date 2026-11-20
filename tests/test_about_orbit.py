"""Public About page: content, scoped styles and safe asset resolution."""
from unittest.mock import patch

import pytest
from django.templatetags.static import static
from django.urls import reverse

from apps.public.views import ABOUT_ART


@pytest.mark.django_db
def test_about_orbit_content_and_scope(client, customer_user):
    response = client.get(reverse("public:about"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "orbit-about" in html
    assert html.count("<h1") == 1
    assert html.count('class="ab-glass ab-value ab-value-') == 3
    assert static("css/about-orbit.css") in html
    assert static("js/about-orbit.js") in html
    assert "خود را نماینده رسمی یا بخشی از شرکت تلگرام معرفی نمی‌کند" in html
    for section in ("about-story", "product-principles", "about-independence"):
        assert f'id="{section}"' in html
        assert f'href="#{section}"' in html
    for role in ABOUT_ART:
        assert f'data-about-art="{role}"' in html
        assert response.context["about_art"][role] in html
    assert reverse("accounts:register") in html
    for route in ("public:home", "public:faq", "public:terms", "public:contact"):
        other = client.get(reverse(route)).content.decode()
        assert static("css/about-orbit.css") not in other
        assert static("js/about-orbit.js") not in other
    client.force_login(customer_user)
    assert reverse("campaigns:wizard_new") in client.get(reverse("public:about")).content.decode()


@pytest.mark.django_db
def test_about_asset_resolution(client):
    with patch("apps.public.views.finders.find", return_value="present"):
        response = client.get(reverse("public:about"))
        for role, (path, _) in ABOUT_ART.items():
            assert response.context["about_art"][role] == static(path)
    with patch("apps.public.views.finders.find", return_value=None), patch(
        "apps.public.views.feature_asset", return_value="/static/fallback.webp"
    ):
        response = client.get(reverse("public:about"))
        assert set(response.context["about_art"].values()) == {"/static/fallback.webp"}
