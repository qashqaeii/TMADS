"""Home markup, routing and artwork regressions."""
import pytest
from django.contrib.staticfiles import finders
from django.urls import reverse

from scripts.optimize_landing_assets import SPECS


@pytest.mark.django_db
def test_landing_art_and_sections(client):
    response = client.get(reverse("public:home"))
    assert response.status_code == 200
    html = response.content.decode()
    for asset in SPECS:
        assert finders.find(f"img/landing/{asset}.png")
        assert f"img/landing/{asset}." in html
    for section in ("home-targeting", "home-process", "telegram-ads-guide", "home-faq"):
        assert f'id="{section}"' in html
    assert "orbit-landing" in html
    assert "landing-orbit" in html
    assert html.count("<h1") == 1
    assert html.count("<details") == 4
    assert reverse("accounts:register") in html
    assert reverse("public:pricing") in html


@pytest.mark.django_db
def test_landing_styles_are_home_only(client):
    html = client.get(reverse("public:features")).content.decode()
    assert "landing-orbit.css" not in html
    assert "orbit-footer-art" not in html
