import pytest
from django.urls import reverse

from apps.campaigns.models import Campaign


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("step", "heading", "field"),
    [
        (1, "هدف و مقصد کمپین را مشخص کنید", 'name="target_type"'),
        (2, "مخاطب مناسب را انتخاب کنید", 'name="channel_mode"'),
        (3, "پیام تبلیغ را بسازید", 'name="ad_text"'),
        (4, "بودجه و زمان اجرا را تنظیم کنید", 'name="budget_toman"'),
        (5, "پیش از ثبت، همه‌چیز را مرور کنید", 'name="terms_accepted"'),
    ],
)
def test_campaign_studio_renders_premium_guided_steps(client, customer_user, step, heading, field):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="کمپین آزمایشی",
        target_type=Campaign.TargetType.CHANNELS,
        placement="channel_post",
        destination="https://t.me/example",
        wizard_version=2,
        wizard_step=step,
    )
    client.force_login(customer_user)

    response = client.get(reverse("campaigns:wizard", kwargs={"campaign_id": campaign.id}))

    assert response.status_code == 200
    html = response.content.decode()
    assert 'id="campaign-studio"' in html
    assert 'id="campaign-studio-form"' in html
    assert 'class="studio-stepper__list"' in html
    assert 'id="draft-save-status"' in html
    assert 'id="studio-preview-panel"' in html
    assert "campaign-studio-premium" in html
    assert heading in html
    assert field in html
    assert html.count('aria-current="step"') == 1
