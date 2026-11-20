"""Shared identity contract across public, authentication and admin pages."""
import json
import re

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse

from apps.public.seo import PAGES


MARK = "img/logo/gramads-logo-mark.webp"
FULL = "img/logo/gramads-logo-full.webp"


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["public:" + name for name in PAGES] + [
    "accounts:login", "accounts:register", "accounts:password_reset",
])
def test_public_brand(client, route):
    response = client.get(reverse(route))
    assert response.status_code == 200
    html = response.content.decode()
    assert "گرام‌ادز" in html
    assert "تی‌ام‌ادز" not in html
    assert static(MARK) in html
    assert static("css/gramads-brand.css") in html
    if route.startswith("public:"):
        assert static(FULL) in html


def test_logo_files_present():
    assert finders.find(MARK)
    assert finders.find(FULL)


@pytest.mark.django_db
def test_dashboard_brand(client, customer_user):
    client.force_login(customer_user)
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "گرام‌ادز" in html
    assert "تی‌ام‌ادز" not in html
    assert static(MARK) in html


@pytest.mark.django_db
def test_admin_brand(client):
    response = client.get(reverse("admin:login"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "گرام‌ادز" in html
    assert static(MARK) in html


@pytest.mark.django_db
def test_public_schema_brand(client, settings):
    settings.PUBLIC_SITE_URL = "https://gramads.ir"
    settings.APP_ENV = "PRODUCTION"
    html = client.get(reverse("public:home")).content.decode()
    data = json.loads(re.search(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    ).group(1))
    website, organization = data["@graph"]
    assert website["alternateName"] == "GramAds"
    assert organization["name"] == "گرام‌ادز"
    assert organization["logo"] == "https://gramads.ir" + static(FULL)
