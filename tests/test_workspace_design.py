"""Server-rendered internal UI contract; no financial or provider writes."""
import pytest
from django.templatetags.static import static
from django.contrib.staticfiles import finders
from django.urls import reverse

CUSTOMER_PAGES = [
    ("/campaigns/", "ui-campaign-list"),
    ("/accounts/advertiser-account/", "ui-account-page"),
    ("/accounts/advertiser-assets/", "ui-assets"),
    ("/finance/wallet/", "ui-finance"),
    ("/finance/invoices/", "ui-finance"),
    ("/finance/refunds/", "ui-finance"),
    ("/finance/transactions/", "ui-finance"),
    ("/app/ad-policies/", "ui-policy-center"),
    ("/support/", "ui-support"),
    ("/support/new/", "ui-support"),
    ("/accounts/profile/", "ui-account-page"),
    ("/app/notifications/", "ga-notifications"),
]

@pytest.mark.django_db
@pytest.mark.parametrize("path,marker", CUSTOMER_PAGES)
def test_workspace_visual_contract(client, customer_user, path, marker):
    client.force_login(customer_user)
    response = client.get(path)
    assert response.status_code == 200, path
    html = response.content.decode()
    assert marker in html
    assert static("css/gramads-workspace-pages.css") in html
    assert static("css/gramads-workspace-composition.css") in html
    assert static("css/gramads-sidebar.css") in html
    assert static("css/gramads-workspace-background.css") in html
    assert 'is-app ga-workspace-system' in html
    assert html.count('id="ui-confirmation"') == 1
    assert "ga-confirm-dialog" in html
    assert "ga-ws-icon" in html

@pytest.mark.django_db
def test_workspace_summary_preserves_real_data(client, customer_user):
    client.force_login(customer_user)
    html = client.get(reverse("dashboard:home")).content.decode()
    assert html.count("ga-home-metric-icon") == 4
    assert "ga-home-coverage" in html

@pytest.mark.django_db
def test_public_page_does_not_opt_in_to_workspace(client):
    html = client.get("/").content.decode()
    assert 'is-app ga-workspace-system' not in html


@pytest.mark.django_db
@pytest.mark.parametrize("path,marker", [
    ("/accounts/profile/", "ga-profile-identity"),
    ("/accounts/advertiser-account/", "ga-account-top"),
    ("/accounts/advertiser-assets/", "ga-assets-workspace"),
    ("/finance/wallet/", "ga-wallet-summary"),
    ("/finance/refunds/", "ga-steps"),
    ("/finance/invoices/", "ga-data-panel"),
    ("/campaigns/", "ga-campaign-filter"),
    ("/support/", "ga-help-layout"),
    ("/app/ad-policies/", "ga-policy-layout"),
])
def test_dedicated_compositions(client, customer_user, path, marker):
    client.force_login(customer_user)
    response = client.get(path)
    assert response.status_code == 200
    assert marker in response.content.decode()


def test_gramads_main_background_asset_is_valid_webp():
    image = finders.find("img/backgrounds/gramads-dashboard-main-background.webp")
    assert image is not None
    with open(image, "rb") as asset:
        assert asset.read(4) == b"RIFF"
    assert __import__("os").path.getsize(image) < 100_000
