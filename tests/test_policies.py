import pytest

from apps.campaigns.models import AdCreative, Campaign, CampaignTargeting
from apps.policies.constants import FindingSeverity, OperatorAuthorizationState
from apps.policies.models import OperatorAdvertisingAuthorization
from apps.policies.services.engine import evaluate_campaign
from apps.policies.services.preflight import CampaignPolicyPreflight, assert_submission_ready
from apps.policies.services.content_rules import scan_prohibited_hints
from apps.policies.services.text_rules import check_ad_text, check_text_links


def test_prohibited_hint_does_not_match_inside_persian_words():
    assert scan_prohibited_hints("ربات فیلترشکن با آی‌پی ثابت") == []
    assert scan_prohibited_hints("پنجره شیشه‌ای خانه") == []
    assert any(f.rule_id == "TG-PRH-005" for f in scan_prohibited_hints("سایت بت آنلاین"))
    assert any(f.rule_id == "TG-PRH-005" for f in scan_prohibited_hints("مصرف شیشه ممنوع"))


@pytest.mark.django_db
def test_text_length_blocked():
    findings = check_ad_text("channels", "a" * 161)
    assert any(f.severity == FindingSeverity.BLOCKED for f in findings)


@pytest.mark.django_db
def test_search_skips_ad_text():
    assert check_ad_text("search", "x" * 200) == []


@pytest.mark.django_db
def test_line_break_blocked():
    findings = check_ad_text("bots", "سلام\nدنیای")
    assert any(f.severity == FindingSeverity.BLOCKED for f in findings)


@pytest.mark.django_db
def test_multiple_text_links_blocked():
    text = "برو @aaaa و @bbbb"
    findings = check_text_links(text, "https://t.me/aaaa")
    assert any(f.severity == FindingSeverity.BLOCKED for f in findings)


@pytest.mark.django_db
def test_link_mismatch_blocked():
    findings = check_text_links("برو @other", "https://t.me/mybot")
    assert any(f.severity == FindingSeverity.BLOCKED for f in findings)


@pytest.mark.django_db
def test_bot_destination_does_not_trigger_channel_activity_warning(customer_user):
    from apps.policies.services.destination_rules import check_destination_readiness, destination_looks_like_bot

    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        target_type="bots",
        placement="bot_banner",
        destination="https://t.me/HyperTunnelbot?start=start",
        wizard_version=2,
    )
    assert destination_looks_like_bot(campaign) is True
    findings = check_destination_readiness(campaign)
    messages = [f.message_fa for f in findings]
    assert not any("کانال باید فعال باشد" in msg for msg in messages)
    rights = next(f for f in findings if "حق قانونی" in f.message_fa)
    assert rights.field_key == "destination_rights_confirmed"
    assert any("ربات" in msg for msg in messages)


@pytest.mark.django_db
def test_step1_saves_destination_rights_confirmation(customer_user):
    from apps.campaigns.studio import apply_studio_step
    from apps.policies.services.destination_rules import check_destination_readiness

    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        target_type="bots",
        placement="bot_banner",
        destination="https://t.me/HyperTunnelbot?start=start",
        wizard_version=2,
        wizard_step=1,
    )
    apply_studio_step(
        campaign,
        1,
        {
            "target_type": "bots",
            "campaign_name": "تست",
            "destination": "https://t.me/HyperTunnelbot?start=start",
            "destination_rights_confirmed": "1",
        },
    )
    campaign.save()
    campaign.refresh_from_db()
    assert campaign.ad_settings.get("destination_rights_confirmed") is True
    assert not any(
        "حق قانونی" in f.message_fa
        for f in check_destination_readiness(campaign)
    )


@pytest.mark.django_db
def test_draft_saves_despite_policy(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        target_type="channels",
        placement="channel_post",
        destination="https://t.me/test",
        wizard_version=2,
    )
    AdCreative.objects.create(campaign=campaign, ad_text="x" * 200)
    run = evaluate_campaign(campaign, strict=False)
    assert run.blocked


@pytest.mark.django_db
def test_preflight_persists_findings(customer_user):
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        target_type="bots",
        placement="bot_banner",
        destination="https://t.me/bot",
        wizard_version=2,
        ad_settings={"terms_accepted": True},
    )
    AdCreative.objects.create(campaign=campaign, ad_text="متن ساده")
    CampaignTargeting.objects.create(campaign=campaign, config={"bot_ids": ["@vote"]})
    result = CampaignPolicyPreflight(campaign).run(
        strict=True, context="test", check_operator=False
    )
    assert result.evaluation_id
    assert campaign.policy_evaluations.exists()


@pytest.mark.django_db
def test_submission_blocked_without_operator_gate(customer_user):
    OperatorAdvertisingAuthorization.objects.create(
        state=OperatorAuthorizationState.PENDING,
        is_current=True,
    )
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        target_type="bots",
        placement="bot_banner",
        destination="https://t.me/bot",
        name="x",
        budget_irr=1_000_000,
        cpm_bid=1,
        wizard_version=2,
        ad_settings={"terms_accepted": True, "destination_rights_confirmed": True},
    )
    AdCreative.objects.create(campaign=campaign, ad_text="متن")
    CampaignTargeting.objects.create(campaign=campaign, config={"bot_ids": ["@vote"]})
    with pytest.raises(ValueError):
        assert_submission_ready(campaign)


@pytest.mark.django_db
def test_submission_allowed_with_operator_approved(customer_user):
    OperatorAdvertisingAuthorization.objects.filter(is_current=True).update(is_current=False)
    OperatorAdvertisingAuthorization.objects.create(
        state=OperatorAuthorizationState.APPROVED,
        is_current=True,
        documented_basis="test fixture",
    )
    campaign = Campaign.objects.create(
        customer=customer_user.customer_profile,
        target_type="bots",
        placement="bot_banner",
        destination="https://t.me/bot",
        name="x",
        budget_irr=1_000_000,
        cpm_bid=1,
        wizard_version=2,
        ad_settings={
            "terms_accepted": True,
            "destination_rights_confirmed": True,
            "bot_functional_confirmed": True,
        },
    )
    AdCreative.objects.create(campaign=campaign, ad_text="متن کوتاه")
    CampaignTargeting.objects.create(campaign=campaign, config={"bot_ids": ["@vote"]})
    result = assert_submission_ready(campaign)
    assert result.submission_ready


@pytest.mark.django_db
def test_cross_tenant_policy_evaluation_isolated(customer_user):
    from apps.accounts.models import User

    other = User.objects.create_user(username="other2", password="pass1234", role=User.Role.CUSTOMER)
    other_profile = other.customer_profile
    c1 = Campaign.objects.create(customer=customer_user.customer_profile, destination="https://t.me/a")
    c2 = Campaign.objects.create(customer=other_profile, destination="https://t.me/b")
    CampaignPolicyPreflight(c1).run(strict=False, context="iso", check_operator=False)
    assert c2.policy_evaluations.count() == 0
