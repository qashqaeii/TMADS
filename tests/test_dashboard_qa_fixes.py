import re

import pytest
from django.urls import reverse

from apps.campaigns.metrics import build_campaign_list_rows, optimize_campaign_list_queryset
from apps.campaigns.models import Campaign


@pytest.mark.django_db
def test_dashboard_header_does_not_render_stray_action_count(client, customer_user):
    """Regression: portfolio total_actions must not leak into dash_header__actions."""
    customer = customer_user.customer_profile
    for i in range(3):
        Campaign.objects.create(
            customer=customer,
            name=f"c-{i}",
            status=Campaign.Status.ACTIVE,
            destination=f"https://t.me/test{i}",
        )
    campaigns = optimize_campaign_list_queryset(Campaign.objects.filter(customer=customer))
    rows = build_campaign_list_rows(campaigns)
    from apps.campaigns.metrics import aggregate_portfolio_kpis

    total_actions = int(aggregate_portfolio_kpis(rows)["total_actions"])
    client.login(username=customer_user.username, password="pass1234")
    response = client.get(reverse("dashboard:home"))
    html = response.content.decode()
    assert response.status_code == 200
    if total_actions:
        # Raw count must not appear alone inside header actions slot
        assert not re.search(
            r'<div class="dash-header__actions">\s*' + re.escape(str(total_actions)) + r"\s*</div>",
            html,
        )
    assert "کیف پول" in html
    assert "ساخت تبلیغ" in html
    assert "کمپین جدید" in html


@pytest.mark.django_db
def test_telegram_remote_status_filter():
    from apps.core.templatetags.core_filters import telegram_remote_status_fa

    assert telegram_remote_status_fa("active") == "فعال در تلگرام"
    assert telegram_remote_status_fa("") == "—"
