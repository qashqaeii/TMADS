import pytest
from django.urls import reverse
from apps.accounts.models import User
from apps.campaigns.models import Campaign, TelegramAdvertisement


@pytest.mark.django_db
def test_ops_cannot_promote_unpaid_campaign_or_link_arbitrary_remote(client, customer_user):
    admin = User.objects.create_user(username="ops-test", role=User.Role.ADMIN, password="pass1234")
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, name="Unpaid")
    client.force_login(admin)
    url = reverse("operations:campaign_review", args=[campaign.id])
    for action in ("approve", "reject", "link_ad"):
        assert client.post(url, {"action": action, "remote_ad_id": "9999"}).status_code == 302
        campaign.refresh_from_db()
        assert campaign.status == Campaign.Status.DRAFT
        assert not TelegramAdvertisement.objects.filter(campaign=campaign).exists()
