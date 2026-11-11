import pytest
from django.urls import reverse

from apps.campaigns.models import Campaign


@pytest.mark.django_db
def test_campaign_list_empty_state_no_campaigns(client, customer_user):
    client.login(username=customer_user.username, password="pass1234")
    response = client.get(reverse("campaigns:list"))
    assert response.status_code == 200
    assert "هنوز کمپینی ندارید" in response.content.decode()


@pytest.mark.django_db
def test_campaign_list_empty_state_filtered(client, customer_user):
    Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="فیلتر",
        destination="https://t.me/x",
    )
    client.login(username=customer_user.username, password="pass1234")
    response = client.get(reverse("campaigns:list"), {"q": "ناموجود"})
    assert response.status_code == 200
    assert "نتیجه‌ای با این فیلتر نیست" in response.content.decode()


@pytest.mark.django_db
def test_campaign_list_advanced_columns_toggle_markup(client, customer_user):
    Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="ستون",
        destination="https://t.me/y",
    )
    client.login(username=customer_user.username, password="pass1234")
    response = client.get(reverse("campaigns:list"))
    html = response.content.decode()
    assert "campaign-advanced-cols" in html
    assert "col-advanced" in html
