import pytest
from django.urls import reverse
from apps.campaigns.models import Campaign, AdCreative


@pytest.mark.django_db
def test_policy_preview_does_not_save_or_mutate_paid_campaign(client, customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile,
        target_type="channels", placement="channel_post", wizard_step=3)
    creative = AdCreative.objects.create(campaign=campaign, ad_text="original")
    client.force_login(customer_user)
    url = reverse("campaigns:policy_preview", args=[campaign.id])
    payload = {"studio_step": 3, "draft_revision": 0, "ad_text": "temporary"}
    assert client.post(url, payload).status_code == 200
    creative.refresh_from_db()
    assert creative.ad_text == "original"
    campaign.status = Campaign.Status.PENDING_REVIEW
    campaign.save(update_fields=["status"])
    assert client.post(url, payload).status_code == 409


@pytest.mark.django_db
def test_stale_autosave_and_manual_post_cannot_overwrite(client, customer_user):
    campaign = Campaign.objects.create(customer=customer_user.customer_profile, target_type="search",
        wizard_step=1, name="Latest", draft_revision=2)
    client.force_login(customer_user)
    payload = {"studio_step": 1, "draft_revision": 1, "campaign_name": "Stale", "action": "save_draft"}
    assert client.post(reverse("campaigns:autosave", args=[campaign.id]), payload).status_code == 409
    assert client.post(reverse("campaigns:wizard", args=[campaign.id]), payload).status_code == 302
    campaign.refresh_from_db()
    assert campaign.name == "Latest"
    assert campaign.draft_revision == 2
