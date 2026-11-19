import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.campaigns.models import Campaign, CampaignTargeting, TelegramAdvertisement
from apps.campaigns.deletion import can_delete_draft_campaign
from apps.campaigns.studio import migrate_campaign_to_studio
from apps.telegram_ads.targeting.normalize import safe_destination_link


def test_destination_link_rejects_active_content():
    for value in ("javascript:alert(1)", "data:text/html,x", "//evil.example", "https://a.example\\@evil.example"):
        assert not safe_destination_link(value)
    assert safe_destination_link("https://t.me/example") == "https://t.me/example"


@pytest.mark.django_db
def test_duplicate_is_post_only_and_resets_acceptance(client, customer_user):
    original = Campaign.objects.create(customer=customer_user.customer_profile, name="A", ad_settings={"terms_accepted": True})
    client.force_login(customer_user)
    url = reverse("campaigns:duplicate", args=[original.pk])
    assert client.get(url).status_code == 405
    assert client.post(url).status_code == 302
    clone = Campaign.objects.exclude(pk=original.pk).get(customer=original.customer)
    assert clone.status == Campaign.Status.DRAFT
    assert not clone.ad_settings.get("terms_accepted")


@pytest.mark.django_db
def test_linked_draft_is_not_deletable(customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, name="A")
    TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id="100")
    assert not can_delete_draft_campaign(campaign)[0]


@pytest.mark.django_db
def test_legacy_wizard_step_is_mapped_before_version_change(customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, wizard_version=1, wizard_step=4)
    migrate_campaign_to_studio(campaign)
    assert campaign.wizard_step == 2


@pytest.mark.django_db
def test_support_cannot_attach_another_customers_campaign(client, customer_user):
    other = User.objects.create_user(username="someoneelse", password="x")
    campaign = Campaign.objects.create(customer=other.customer_profile, name="Other")
    client.force_login(customer_user)
    assert client.post(reverse("support:create"), {"campaign_id": str(campaign.pk), "subject": "test", "body": "test"}).status_code == 404
