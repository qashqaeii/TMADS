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
    assert "campaign-studio-refinements" in html
    assert heading in html
    assert field in html
    assert html.count('aria-current="step"') == 1
    assert "CAMPAIGN WORKSPACE" not in html
    assert "LIVE CAMPAIGN PREVIEW" not in html
    assert "Telegram Ads" not in html
    assert "Sponsored placement" not in html
    assert "timesince" not in html
    assert 'type="datetime-local"' not in html
    if step == 4:
        assert 'name="schedule_start" type="text"' in html
        assert 'name="schedule_end" type="text"' in html
        assert "۱۴۰۵/۰۹/۳۰" in html


def test_campaign_preview_keeps_currency_labels_persian():
    from pathlib import Path
    from django.conf import settings

    template = (settings.BASE_DIR / "templates/campaigns/includes/studio_preview.html").read_text(encoding="utf-8")
    assert "ton_allocation|persian_digits" in template
    assert " TON</small>" not in template
    assert "LIVE CAMPAIGN PREVIEW" not in template
    assert "Sponsored placement" not in template
