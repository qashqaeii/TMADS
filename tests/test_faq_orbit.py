"""FAQ redesign keeps native content, scoped assets and safe illustration fallbacks."""
from unittest.mock import patch

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse
from PIL import Image

from apps.public.views import FAQ_ART_FALLBACKS


@pytest.mark.django_db
def test_faq_orbit_content_and_scope(client, customer_user):
    html = client.get(reverse("public:faq")).content.decode()
    assert "orbit-faq" in html
    assert html.count("data-fq-question>") == 16
    assert html.count('data-fq-group="') == 5
    assert html.count('class="fq-glass fq-guide-card"') == 4
    assert static("css/faq-orbit.css") in html
    assert static("js/faq-orbit.js") in html
    assert "{% load faq_assets" not in html
    for role in FAQ_ART_FALLBACKS:
        assert f'data-faq-art="{role}"' in html
    assert reverse("accounts:register") in html
    for route in ("public:home", "public:features", "public:pricing", "public:how_it_works"):
        other = client.get(reverse(route)).content.decode()
        assert static("css/faq-orbit.css") not in other
        assert static("js/faq-orbit.js") not in other
    client.force_login(customer_user)
    assert reverse("campaigns:wizard_new") in client.get(reverse("public:faq")).content.decode()


@pytest.mark.django_db
def test_faq_art_prefers_exact_names_and_has_fallback(client):
    with patch("apps.public.views.finders.find", return_value=None), patch(
        "apps.public.views.feature_asset", return_value="/static/fallback.webp"
    ):
        response = client.get(reverse("public:faq"))
        assert response.status_code == 200
        assert set(response.context["faq_art"].values()) == {"/static/fallback.webp"}
    with patch("apps.public.views.finders.find", return_value="present"), patch(
        "apps.public.views.static", side_effect=lambda path: path
    ):
        response = client.get(reverse("public:faq"))
        for role in FAQ_ART_FALLBACKS:
            path = f"img/faq/tmads_faq_{role}.webp"
            assert response.context["faq_art"][role] == path
    for role in FAQ_ART_FALLBACKS:
        source = finders.find(f"img/faq/tmads_faq_{role}.webp")
        if source:
            with Image.open(source) as image:
                assert image.format == "WEBP"
                assert image.getchannel("A").getextrema() == (0, 255)
