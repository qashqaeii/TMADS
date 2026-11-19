"""Render and template regression checks for the final UI pass (no live writes)."""
from pathlib import Path

import pytest
from django.template.loader import get_template
from django.templatetags.static import static
from django.test import SimpleTestCase
from django.urls import reverse


def test_all_project_html_templates_compile():
    root = Path(__file__).resolve().parents[1] / "templates"
    paths = sorted(root.rglob("*.html"))
    assert paths
    for path in paths:
        get_template(path.relative_to(root).as_posix())


@pytest.mark.django_db
@pytest.mark.parametrize("route", [
    "public:home", "public:features", "public:how_it_works", "public:pricing",
    "public:faq", "public:contact", "public:about", "public:terms",
    "public:privacy", "public:refund", "public:content_policy", "accounts:login",
    "accounts:register", "accounts:password_reset",
    "accounts:password_reset_done", "accounts:password_reset_complete",
])
def test_public_ui_shell(client, route):
    response = client.get(reverse(route))
    assert response.status_code == 200, route
    # Manifest storage adds a content hash after collectstatic (as in CI).
    # Verify the exact stylesheet link, not an unhashed filename substring.
    stylesheet = static('css/ui-foundation.css')
    SimpleTestCase().assertContains(
        response, f'<link rel="stylesheet" href="{stylesheet}">', html=True,
    )
    assert b'id="ui-confirmation"' in response.content
    assert b'dir="rtl"' in response.content


@pytest.mark.django_db
@pytest.mark.parametrize("route", [
    "dashboard:home", "dashboard:notifications", "campaigns:list",
    "finance:wallet", "finance:topup", "finance:transactions",
    "finance:invoices", "finance:refunds", "support:list", "support:create",
    "accounts:profile", "policies:ad_policies",
    "accounts:related_account", "accounts:related_ads", "accounts:advertiser_assets",
])
def test_customer_ui_shell(client, customer_user, route):
    client.force_login(customer_user)
    response = client.get(reverse(route))
    assert response.status_code == 200, route
    assert b'ui-shell' in response.content
    assert b'id="main-content"' in response.content
    assert b'id="ui-confirmation"' in response.content


@pytest.mark.django_db
def test_draft_detail_and_wizard_markup(client, customer_user):
    from apps.campaigns.models import Campaign

    client.force_login(customer_user)
    draft = Campaign.objects.create(customer=customer_user.customer_profile, name="UI test draft")
    detail = client.get(reverse("campaigns:detail", args=[draft.id]))
    assert detail.status_code == 200
    wizard = client.get(reverse("campaigns:wizard", args=[draft.id]))
    assert wizard.status_code == 200
    assert b'ui-studio' in wizard.content
    assert b'draft_revision' in wizard.content
    assert b'csrfmiddlewaretoken' in wizard.content
    assert b'aria-current="step"' in wizard.content


@pytest.mark.django_db
def test_related_ads_empty_state_does_not_contact_api(client, customer_user):
    from unittest.mock import patch

    client.force_login(customer_user)
    with patch("apps.telegram_ads.account_ad_views.verified_client") as api:
        response = client.get(reverse("accounts:related_ads"))
        assert response.status_code == 200
        assert b'ui-assets' in response.content
        assert b'ui-empty' in response.content
        api.assert_not_called()


@pytest.mark.django_db
def test_release_workspace_uses_shared_shell(client, customer_user):
    from apps.accounts.models import User

    url = reverse("operations:release_readiness")
    client.force_login(customer_user)
    assert client.get(url).status_code == 403
    manager = User.objects.create_user(username="ui-ops-review", role=User.Role.ADMIN)
    client.force_login(manager)
    response = client.get(url)
    assert response.status_code == 200
    assert b'ui-release-checks' in response.content
    assert b'ui-final' in response.content
