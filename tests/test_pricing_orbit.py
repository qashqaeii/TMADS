"""Pricing design uses the uploaded artwork and does not invoke finance services."""
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse
from PIL import Image


ART = ("hero_orbit", "wallet_and_coins", "discount_badge", "cpm_calculator",
       "invoice_checklist", "refund_cycle", "roi_target")


@pytest.mark.django_db
def test_pricing_orbit_assets_and_financial_boundary(client):
    with patch("apps.finance.services.campaign_pricing.build_campaign_quote") as quote:
        response = client.get(reverse("public:pricing"))
        quote.assert_not_called()
    assert response.status_code == 200
    html = response.content.decode()
    for role in ART:
        path = f"img/pricing/tmads_pricing_{role}.webp"
        assert static(path) in html
        source = finders.find(path)
        assert source
        with Image.open(Path(source)) as image:
            assert image.format == "WEBP"
            assert image.getchannel("A").getextrema() == (0, 255)
    assert "orbit-pricing" in html
    assert static("css/pricing-orbit.css") in html
    assert static("js/pricing-orbit.js") in html
    assert html.count("<h1") == 1
    for section in ("pricing-model", "pricing-cpm", "budget-decisions"):
        assert f'id="{section}"' in html
    assert "data-pr-calculator hidden" in html
    assert 'id="pr-calc-example"' in html
    assert reverse("accounts:register") in html


@pytest.mark.django_db
def test_pricing_assets_scoped_and_authenticated_conversion(client, customer_user):
    for route in ("public:home", "public:features", "accounts:login"):
        html = client.get(reverse(route)).content.decode()
        assert static("css/pricing-orbit.css") not in html
        assert static("js/pricing-orbit.js") not in html
    client.force_login(customer_user)
    html = client.get(reverse("public:pricing")).content.decode()
    assert reverse("campaigns:wizard_new") in html
