import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_dashboard_composition_markup(client, customer_user):
    client.login(username=customer_user.username, password="pass1234")
    html = client.get(reverse("dashboard:home")).content.decode()
    assert "dash-home" in html
    assert "dash-kpi-board" in html
    assert "dash-workspace" in html
    assert "dash-hero" in html
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
