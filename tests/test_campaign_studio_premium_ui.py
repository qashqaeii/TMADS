import pytest
from django.test import override_settings
from django.urls import reverse

from apps.campaigns.models import Campaign


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("step", "heading", "field"),
    [
        (1, "کجا می‌خوای تبلیغ نمایش داده بشه؟", 'name="target_type"'),
        (2, "می‌خوای کی این تبلیغ رو ببینه؟", 'data-field="language_codes"'),
        (3, "متن تبلیغ‌ت چی باشه؟", 'name="ad_text"'),
        (4, "چقدر می‌خوای هزینه کنی و از کی شروع بشه؟", 'name="budget_toman"'),
        (5, "همه‌چی درسته؟ یه نگاه آخر بنداز", 'name="terms_accepted"'),
    ],
)
@override_settings(DEBUG=True, APP_ENV="LOCAL", ARVAN_AI_ENABLED=False)
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
    assert "studio-stepper__btn" in html
    assert 'id="draft-save-status"' in html
    assert 'id="studio-preview-panel"' in html
    assert "tg-ads-preview" in html
    assert "telegramWallpaper" in html
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
    assert 'id="studio-policy-panel"' in html
    assert "policy-panel__summary" in html
    assert "<details" in html
    assert "بررسی قوانین" in html
    policy_tag = html.split('id="studio-policy-panel"', 1)[0].rsplit("<details", 1)[-1]
    assert " open" not in policy_tag.split(">", 1)[0]
    if step == 1:
        assert 'data-tm-ai="planner"' in html
        assert "ui-ai.css" in html
        assert "ui-ai.js" in html
    if step == 3:
        assert 'data-tm-ai="creative"' in html
        assert "ui-ai.css" in html
    if step == 4:
        assert 'name="schedule_start"' in html
        assert 'name="schedule_end"' in html
        assert "data-jalali-datetime" in html
        assert "studio-jalali-picker.js" in html
        assert "تعیین زمان پایان" in html
        assert "افزودن سقف روزانه" in html
        assert "data-money-input" in html
        assert "data-money-raw" in html
        assert "studio-field-tip" in html
        assert "data-studio-tip" in html
        assert "data-tip=" in html
        assert "studio-field-tip__glyph" in html
        assert "پیشنهاد نمایش" in html
        assert "studio-finance__columns" in html
        assert "پانصد میلیون تومان" not in html
        assert "واحد ورودی «هزار تومان»" not in html
        assert "حداقل بودجه معادل ۱ گرام" in html
        assert "۱۰۰٬۰۰۰ تومان است" not in html
        assert "studio-finance__live-rate" in html
        assert "قیمت گرام" in html
        assert "افزایش نرخ" not in html
        assert "نوبیتکس" not in html
        assert "عنوان تبلیغ" in html
        assert "کد داخلی تبلیغ" not in html
        assert 'name="campaign_name"' in html


def test_campaign_preview_keeps_currency_labels_persian():
    from pathlib import Path
    from django.conf import settings

    template = (settings.BASE_DIR / "templates/campaigns/includes/studio_preview.html").read_text(encoding="utf-8")
    assert "ton_allocation|format_ton" in template
    assert " TON</small>" not in template
    assert "LIVE CAMPAIGN PREVIEW" not in template
    assert "Sponsored placement" not in template


def test_budget_money_inputs_use_direct_toman_unit():
    from pathlib import Path
    from django.conf import settings

    template = (settings.BASE_DIR / "templates/campaigns/wizard.html").read_text(encoding="utf-8")
    assert 'id="studio-control-16-unit">تومان</span>' in template
    assert 'id="studio-control-17-unit">تومان</span>' in template
    assert "studio-control-16-unit\">هزار تومان" not in template
    assert "tip=budget_field_tip" in template
    assert "data-money-input" in template
    assert "budget_irr|irr_to_toman" in template


@pytest.mark.django_db
def test_single_placement_targets_hide_placement_chooser(client, customer_user):
    """bots/channels/search only have one placement — no fake multi-choice card."""
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="ربات آزمایشی",
        target_type=Campaign.TargetType.BOTS,
        placement="bot_banner",
        destination="https://t.me/HyperTunnelbot",
        wizard_version=2,
        wizard_step=2,
    )
    client.force_login(customer_user)
    html = client.get(reverse("campaigns:wizard", kwargs={"campaign_id": campaign.id})).content.decode()
    assert "تبلیغ کجا دیده بشه؟" not in html
    assert 'type="radio" name="placement"' not in html
    assert 'name="placement" value="bot_banner"' in html
    assert 'name="bot_ids"' in html or "data-bot-selector" in html
    assert 'data-preview-shell="bot_banner"' in html
    assert "tg-ads-preview__bot-shell" in html
    assert "tg-ads-preview__feed--bot" in html
    assert "tg-ads-preview__top-slot" in html
    assert "tg-ads-preview__phone" in html
    # ترتیب DOM: هدر ربات → بنر تبلیغ → اسکلت چت
    bot_bar = html.index("tg-ads-preview__bot-bar")
    top_slot = html.index("tg-ads-preview__top-slot")
    feed_bot = html.index("tg-ads-preview__feed--bot")
    assert bot_bar < top_slot < feed_bot


@pytest.mark.django_db
def test_users_target_still_shows_placement_chooser(client, customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="کاربر آزمایشی",
        target_type=Campaign.TargetType.USERS,
        placement="channel_post",
        destination="https://t.me/example",
        wizard_version=2,
        wizard_step=2,
    )
    client.force_login(customer_user)
    html = client.get(reverse("campaigns:wizard", kwargs={"campaign_id": campaign.id})).content.decode()
    assert "تبلیغ کجا دیده بشه؟" in html
    assert "بنر در ربات" in html
    assert "پیام اسپانسری در کانال" in html
    assert "بنر روی ویدیو" in html
    assert html.index("پیام اسپانسری در کانال") < html.index("بنر روی ویدیو") < html.index("بنر در ربات")
    assert 'data-field="country_codes"' in html
    assert 'data-field="language_codes"' in html
    assert 'data-field="topic_ids"' in html
    assert 'name="channel_ids"' in html
    assert 'name="device"' in html
    assert 'name="political_channels_only"' in html
    assert 'name="exclude_political_channels"' in html
    assert 'data-field="exclude_topic_ids"' in html
    assert 'name="exclude_channel_ids"' in html
    assert "data-preview-cta-label" in html
    assert "tg-ads-preview__cta" in html
    assert "data-location-picker" in html
    assert 'data-preview-shell="channel_post"' in html
    assert 'data-preview-shell="video_banner"' in html
    assert 'data-preview-shell="bot_banner"' in html
    assert "tg-ads-preview__thread--channel-bottom" in html
    assert "tg-ads-preview__bottom-slot" in html
    assert "پایین کانال" in html
    assert "studio-preview__locus-chip" in html
    assert "برای کاربران خاص" in html
    assert "tg-ads-preview__channel-bar" in html
    # ترتیب DOM کانال: هدر → اسکلت فید → تبلیغ پایین
    ch_bar = html.index("tg-ads-preview__channel-bar")
    ch_feed = html.index('class="tg-ads-preview__feed"', ch_bar)
    ch_bottom = html.index("tg-ads-preview__bottom-slot", ch_feed)
    assert ch_bar < ch_feed < ch_bottom


def test_default_users_placement_is_channel_post():
    from apps.telegram_ads.targeting.compatibility import (
        default_placement_for_target,
        placement_choices_for_target,
    )

    assert default_placement_for_target("users") == "channel_post"
    choices = [item["placement"] for item in placement_choices_for_target("users")]
    assert choices == ["channel_post", "video_banner", "bot_banner"]


@pytest.mark.django_db
def test_channels_target_shows_all_telegram_fields(client, customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        name="کانال آزمایشی",
        target_type=Campaign.TargetType.CHANNELS,
        placement="channel_post",
        destination="https://t.me/HyperTunnelbot",
        wizard_version=2,
        wizard_step=2,
    )
    client.force_login(customer_user)
    html = client.get(reverse("campaigns:wizard", kwargs={"campaign_id": campaign.id})).content.decode()
    assert "چطور کانال‌ها رو انتخاب کنم؟" not in html
    assert 'select[name="channel_mode"]' not in html and "<select id=\"studio-control-4\"" not in html
    assert 'data-field="language_codes"' in html
    assert 'data-field="topic_ids"' in html
    assert "data-channel-selector" in html
    assert 'data-similar-channels="' in html
    assert "data-similar-channels-panel" in html
    assert "data-similar-channels-open" in html
    assert "افزودن کانال‌های مشابه" in html
    assert "اگر کانال مشخص انتخاب شده، فیلد زبان باید خالی باشد." in html
    assert 'data-default="fa"' in html or 'name="language_codes" value="fa"' in html
    assert "catalog-suggest--dense" in html
    assert 'data-field="exclude_topic_ids"' in html
    assert 'name="exclude_channel_ids"' in html
    assert "data-preview-cta-label" in html
    assert "tg-ads-preview__cta" in html
    assert 'data-preview-shell="channel_post"' in html
    assert "tg-ads-preview__thread--channel-bottom" in html
    assert "tg-ads-preview__bottom-slot" in html
    assert "پایین کانال" in html
    assert "studio-preview__locus-chip" in html
    assert "داخل کانال‌ها" in html
