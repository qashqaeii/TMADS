import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_dashboard_composition_markup(client, customer_user):
    client.login(username=customer_user.username, password="pass1234")
    html = client.get(reverse("dashboard:home")).content.decode()
    assert "ga-command" in html
    assert "ga-home-metrics" in html
    assert "ga-home-workspace" in html
    assert "ga-home-header" in html
    assert "chart-box--dominant" not in html
    if 'id="dash-chart"' in html:
        assert "chart-box--dash-home" in html


@pytest.mark.django_db
def test_gramads_overview_layout(client, customer_user):
    client.force_login(customer_user)
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "gramads-overview" in html
    assert html.count('role="listitem"') >= 4
    assert "ga-kpi-active" in html
    assert "ga-bottom-rail" in html
    assert "ga-quick-nav" in html
    assert reverse("campaigns:list") in html
    assert reverse("finance:wallet") in html

    
@pytest.mark.django_db
def test_overview_uses_isolated_compact_components(client, customer_user):
    from apps.campaigns.models import Campaign
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, name="Overview regression", status=Campaign.Status.DRAFT, destination="https://t.me/example")
    client.force_login(customer_user)
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200
    html = response.content.decode()
    assert 'ga-home-metric-grid' in html
    assert 'ga-home-campaign-body' in html
    assert 'ga-home-campaign-identity' in html
    assert 'Overview regression' in html
    assert reverse("campaigns:detail", args=[campaign.id]) in html
    assert 'class="dash-campaign-card__body"' not in html

@pytest.mark.django_db
def test_overview_reference_design(client, customer_user):
    from django.templatetags.static import static
    client.force_login(customer_user)
    response = client.get(reverse("dashboard:home"))
    assert response.status_code == 200
    html = response.content.decode()
    assert static("css/gramads-workspace-system.css") in html
    assert "ga-workspace-system" in html
    assert "ga-home-panel-heading" not in html
    assert 'class="ga-ws-icon ga-ws-icon--' in html
    assert "فعالیت اخیر" in html
    assert html.count("ga-home-metric-icon") == 4
