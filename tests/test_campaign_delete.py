import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.campaigns.deletion import can_delete_draft_campaign, delete_draft_campaign
from apps.campaigns.models import Campaign


@pytest.mark.django_db
def test_can_delete_only_draft():
    user = User.objects.create_user(username="del1", password="pass1234")
    customer = user.customer_profile
    draft = Campaign.objects.create(customer=customer, name="d", status=Campaign.Status.DRAFT)
    active = Campaign.objects.create(customer=customer, name="a", status=Campaign.Status.ACTIVE)
    assert can_delete_draft_campaign(draft)[0] is True
    assert can_delete_draft_campaign(active)[0] is False


@pytest.mark.django_db
def test_delete_draft_via_post(client, customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="پیش‌نویس",
        status=Campaign.Status.DRAFT,
    )
    client.login(username=customer_user.username, password="pass1234")
    url = reverse("campaigns:delete", kwargs={"campaign_id": campaign.id})
    response = client.post(url)
    assert response.status_code == 302
    assert not Campaign.objects.filter(id=campaign.id).exists()


@pytest.mark.django_db
def test_cannot_delete_active(client, customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="live",
        status=Campaign.Status.ACTIVE,
    )
    client.login(username=customer_user.username, password="pass1234")
    url = reverse("campaigns:delete", kwargs={"campaign_id": campaign.id})
    response = client.post(url)
    assert response.status_code == 302
    assert Campaign.objects.filter(id=campaign.id).exists()


@pytest.mark.django_db
def test_delete_draft_helper():
    user = User.objects.create_user(username="del2", password="x")
    campaign = Campaign.objects.create(
        customer=user.customer_profile,
        name="x",
        status=Campaign.Status.DRAFT,
    )
    delete_draft_campaign(campaign)
    assert Campaign.objects.filter(customer=user.customer_profile).count() == 0


@pytest.mark.django_db
def test_other_customer_cannot_delete(client):
    u1 = User.objects.create_user(username="o1", password="pass1234")
    u2 = User.objects.create_user(username="o2", password="pass1234")
    c = Campaign.objects.create(customer=u2.customer_profile, name="secret", status=Campaign.Status.DRAFT)
    client.login(username="o1", password="pass1234")
    url = reverse("campaigns:delete", kwargs={"campaign_id": c.id})
    response = client.post(url)
    assert response.status_code == 404
    assert Campaign.objects.filter(id=c.id).exists()
