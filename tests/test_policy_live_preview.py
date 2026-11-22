import pytest
from django.core.cache import cache
from django.urls import reverse

from apps.campaigns.models import Campaign


@pytest.mark.django_db
def test_policy_preview_clears_destination_blocks_when_url_provided(client, customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="کمپین تست قوانین",
        target_type=Campaign.TargetType.CHANNELS,
        placement="channel_post",
        wizard_version=2,
        wizard_step=1,
        destination="",
    )
    client.force_login(customer_user)
    url = reverse("campaigns:policy_preview", args=[campaign.id])
    cache.clear()

    empty = client.post(
        url,
        {
            "studio_step": 1,
            "draft_revision": campaign.draft_revision,
            "target_type": "channels",
            "campaign_name": "کمپین تست قوانین",
            "destination": "",
        },
    )
    assert empty.status_code == 200
    empty_body = empty.json()
    assert empty_body["ok"] is True
    empty_messages = [f["message_fa"] for f in empty_body["findings"]]
    assert any("مقصد" in msg or "آدرس مقصد" in msg for msg in empty_messages)

    cache.clear()
    filled = client.post(
        url,
        {
            "studio_step": 1,
            "draft_revision": campaign.draft_revision,
            "target_type": "channels",
            "campaign_name": "کمپین تست قوانین",
            "destination": "t.me/HyperTunnelbot?start=start",
        },
    )
    assert filled.status_code == 200
    filled_body = filled.json()
    assert filled_body["ok"] is True
    assert "suggestion_fa" in filled_body["findings"][0]
    filled_messages = [f["message_fa"] for f in filled_body["findings"]]
    assert "مقصد تبلیغ تنظیم نشده است." not in filled_messages
    assert "آدرس مقصد تبلیغ الزامی است." not in filled_messages
    campaign.refresh_from_db()
    assert campaign.destination == ""
