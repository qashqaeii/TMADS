import pytest
from decimal import Decimal

from apps.accounts.models import User
from apps.campaigns.metrics import build_campaign_list_rows
from apps.campaigns.models import Campaign, TelegramAdvertisement
from apps.campaigns.performance_insights import build_portfolio_performance_insights


@pytest.mark.django_db
def test_performance_insights_picks_champion_and_lenses():
    user = User.objects.create_user(username="ins1", password="x")
    customer = user.customer_profile
    strong = Campaign.objects.create(customer=customer, name="Strong", status=Campaign.Status.ACTIVE)
    weak = Campaign.objects.create(customer=customer, name="Weak", status=Campaign.Status.ACTIVE)
    TelegramAdvertisement.objects.create(
        campaign=strong,
        remote_ad_id="1",
        remote_status_raw={
            "views": 10000,
            "clicks": 400,
            "actions": 80,
            "spent_budget": "10",
        },
    )
    TelegramAdvertisement.objects.create(
        campaign=weak,
        remote_ad_id="2",
        remote_status_raw={"views": 200, "clicks": 4, "actions": 0, "spent_budget": "0.1"},
    )
    rows = build_campaign_list_rows(Campaign.objects.filter(customer=customer))
    insights = build_portfolio_performance_insights(rows)
    assert insights.champion is not None
    assert insights.champion.campaign_id == strong.id
    assert insights.eligible_count == 2
    assert any(p.lens_key == "reach" for p in insights.lens_winners)
    assert insights.champion.reasons


@pytest.mark.django_db
def test_performance_insights_empty_without_stats():
    user = User.objects.create_user(username="ins2", password="x")
    customer = user.customer_profile
    Campaign.objects.create(customer=customer, name="Draft", status=Campaign.Status.DRAFT)
    rows = build_campaign_list_rows(Campaign.objects.filter(customer=customer))
    insights = build_portfolio_performance_insights(rows)
    assert insights.champion is None
    assert insights.note
