import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.campaigns.models import Campaign


@pytest.mark.django_db
def test_customer_cannot_access_other_campaign(client):
    u1 = User.objects.create_user(username="a", password="pass1234", role=User.Role.CUSTOMER)
    u2 = User.objects.create_user(username="b", password="pass1234", role=User.Role.CUSTOMER)
    c2 = Campaign.objects.create(customer=u2.customer_profile, name="secret")
    client.login(username="a", password="pass1234")
    url = reverse("campaigns:detail", kwargs={"campaign_id": c2.id})
    response = client.get(url)
    assert response.status_code == 404
