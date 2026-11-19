"""Customer safety and read-only API behavior of the remote management surface."""
from unittest.mock import patch

import pytest
from django.urls import reverse

from apps.campaigns.models import Campaign, TelegramAdvertisement, RemoteAdOperation


@pytest.mark.django_db
def test_remote_operation_requires_linked_ad(client, customer_user):
    campaign=Campaign.objects.create(customer=customer_user.customer_profile, name="Unlinked")
    client.force_login(customer_user)
    r=client.get(reverse("campaigns:remote_management",args=[campaign.id]))
    assert r.status_code==302
    assert not RemoteAdOperation.objects.exists()


@pytest.mark.django_db
def test_remote_operation_only_enqueues_without_api_write(client, customer_user):
    campaign=Campaign.objects.create(customer=customer_user.customer_profile,status=Campaign.Status.ACTIVE,name="Linked")
    ad=TelegramAdvertisement.objects.create(campaign=campaign,remote_ad_id="12345",remote_status="active")
    client.force_login(customer_user)
    with patch("apps.telegram_ads.client.TelegramAdsClient") as api:
        url=reverse("campaigns:remote_management",args=[campaign.id])
        assert client.get(url).status_code==200
        assert client.post(url,{"action":"pause"}).status_code==302
        assert RemoteAdOperation.objects.get(advertisement=ad).action=="pause"
        assert client.post(url,{"action":"resume"}).status_code==302
        assert RemoteAdOperation.objects.filter(advertisement=ad).count()==1
        api.assert_not_called()


@pytest.mark.django_db
def test_remote_management_is_tenant_isolated(client, customer_user):
    first=Campaign.objects.create(customer=customer_user.customer_profile)
    user=__import__("apps.accounts.models",fromlist=["User"]).User.objects.create_user(
        username="cust-secondary",password="pass1234",role="customer")
    client.force_login(user)
    assert client.get(reverse("campaigns:remote_management",args=[first.id])).status_code==404


@pytest.mark.django_db
def test_intraday_only_reads_300_second_stats(client, customer_user):
    campaign=Campaign.objects.create(customer=customer_user.customer_profile)
    TelegramAdvertisement.objects.create(campaign=campaign,remote_ad_id="54321")
    client.force_login(customer_user)
    with patch("apps.campaigns.intraday_views.TelegramAdsClient") as api:
        api.return_value.get_ad_statistics.return_value={"items":[{"from_time":1,"views":25,"clicks":2,"currency":"TON","spent_budget":"0.03"}]}
        response=client.get(reverse("campaigns:intraday",args=[campaign.id])+"?hours=6")
        assert response.status_code==200
        assert response.context["total_views"]==25
        assert api.return_value.get_ad_statistics.call_args.kwargs["interval"]==300
