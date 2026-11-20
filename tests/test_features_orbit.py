"""Features assets, routing and progressive enhancement contracts."""
from html.parser import HTMLParser
from unittest.mock import patch

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from PIL import Image

from scripts.optimize_features_assets import TRANSPARENT_ART, optimize
from django.urls import reverse

from apps.core.templatetags.features_assets import FEATURE_ART, feature_asset


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.names = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "img" and "data-feature-art" in attrs:
            self.names.add(attrs["data-feature-art"])
            assert attrs.get("src")
            assert attrs.get("width") and attrs.get("height")
            assert "alt" in attrs


@pytest.mark.django_db
def test_features_orbit_markup(client):
    response = client.get(reverse("public:features"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "orbit-features" in html
    assert static("css/features-orbit.css") in html
    assert static("js/features-orbit.js") in html
    assert html.count('class="fx-card fx-core-card ') == 6
    assert html.count('class="fx-card fx-advanced-card"') == 4
    assert html.count('class="fx-card fx-guide-card"') == 4
    assert html.count("<h1") == 1
    assert reverse("accounts:register") in html
    for id in ("features-core", "features-advanced", "advertiser-toolkit"):
        assert f'id="{id}"' in html
    parser = Images()
    parser.feed(html)
    assert parser.names == set(FEATURE_ART)


@pytest.mark.django_db
def test_features_orbit_is_scoped(client):
    for route in ("public:home", "public:pricing", "accounts:login"):
        html = client.get(reverse(route)).content.decode()
        assert "features-orbit.css" not in html
        assert "features-orbit.js" not in html
        assert 'class="fx-footer-art"' not in html


def test_feature_art_fallback_and_download_path():
    for name, fallback in FEATURE_ART.items():
        with (
            patch("apps.core.templatetags.features_assets.finders.find", return_value=None),
            patch("apps.core.templatetags.features_assets.landing_asset", return_value="fallback-url") as original,
        ):
            assert feature_asset(name) == "fallback-url"
            original.assert_called_once_with(fallback)
        with (
            patch("apps.core.templatetags.features_assets.finders.find", return_value="present"),
            patch("apps.core.templatetags.features_assets.static", side_effect=lambda path: path),
        ):
            preferred = TRANSPARENT_ART.get(name)
            expected = f"{preferred}.optimized.webp" if preferred else f"{name}.webp"
            assert feature_asset(name) == f"img/features/{expected}"


def test_transparent_masters_and_optimizer(tmp_path):
    from shutil import copyfile

    for stem in set(TRANSPARENT_ART.values()):
        filename = f"{stem}.webp"
        source = finders.find(f"img/features/{filename}")
        assert source, filename
        with Image.open(source) as image:
            assert image.format == "WEBP"
            assert "A" in image.getbands()
            assert image.getchannel("A").getextrema() == (0, 255)
        copyfile(source, tmp_path / filename)
    optimize(tmp_path)
    for stem in set(TRANSPARENT_ART.values()):
        target = tmp_path / f"{stem}.optimized.webp"
        with Image.open(target) as image:
            assert image.format == "WEBP"
            assert image.getchannel("A").getextrema() == (0, 255)
            assert max(image.size) <= (1200 if stem == TRANSPARENT_ART["features-hero"] else 480)
        assert target.stat().st_size < (tmp_path / f"{stem}.webp").stat().st_size


def test_transparent_master_used_when_derivative_absent():
    role = "feature-campaign"
    expected = f"img/features/{TRANSPARENT_ART[role]}.webp"
    with (
        patch("apps.core.templatetags.features_assets.finders.find", side_effect=lambda path: path if path == expected else None),
        patch("apps.core.templatetags.features_assets.static", side_effect=lambda path: path),
    ):
        assert feature_asset(role) == expected


@pytest.mark.django_db
def test_features_render_transparent_art_in_all_scenes(client):
    html = client.get(reverse("public:features")).content.decode()
    for stem in set(TRANSPARENT_ART.values()):
        assert f"img/features/{stem}." in html
    assert 'class="fx-hero-halo"' in html
    assert html.count('class="fx-guide-art"') == 4
    assert 'class="fx-cta-orbit"' in html
    assert html.count('class="fx-audience-chip"') == 2
