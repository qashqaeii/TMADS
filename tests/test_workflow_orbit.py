"""Regression contracts for the public workflow journey."""
from unittest.mock import patch

import pytest
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse
from PIL import Image

from apps.core.templatetags.workflow_assets import FALLBACKS, workflow_asset


@pytest.mark.django_db
def test_workflow_markup_and_scope(client, customer_user):
    html = client.get(reverse("public:how_it_works")).content.decode()
    assert "orbit-workflow" in html
    assert static("css/workflow-orbit.css") in html
    assert static("js/workflow-orbit.js") in html
    assert html.count('class="wf-glass wf-step wf-step-') == 6
    assert html.count('data-wf-check>') == 5
    assert html.count("<h1") == 1
    for section in ("guide-steps", "guide-preparation", "campaign-playbook"):
        assert f'id="{section}"' in html
    for role in FALLBACKS:
        assert f'data-workflow-art="{role}"' in html
        assert workflow_asset(role) in html
    assert reverse("accounts:register") in html
    for route in ("public:home", "public:features", "public:pricing", "accounts:login"):
        other = client.get(reverse(route)).content.decode()
        assert static("css/workflow-orbit.css") not in other
        assert static("js/workflow-orbit.js") not in other
    client.force_login(customer_user)
    assert reverse("campaigns:wizard_new") in client.get(reverse("public:how_it_works")).content.decode()


def test_art_resolves_exact_names_or_safe_fallback():
    for role, fallback in FALLBACKS.items():
        path = f"img/workflow/tmads_workflow_{role}.webp"
        with (
            patch("apps.core.templatetags.workflow_assets.finders.find", return_value="present"),
            patch("apps.core.templatetags.workflow_assets.static", side_effect=lambda value: value),
        ):
            assert workflow_asset(role) == path
        with (
            patch("apps.core.templatetags.workflow_assets.finders.find", return_value=None),
            patch("apps.core.templatetags.workflow_assets.feature_asset", return_value="fallback") as original,
        ):
            assert workflow_asset(role) == "fallback"
            original.assert_called_once_with(fallback)
        # Artwork is distributed separately; validate real alpha whenever installed.
        source = finders.find(path)
        if source:
            with Image.open(source) as image:
                assert image.format == "WEBP"
                assert image.getchannel("A").getextrema() == (0, 255)
