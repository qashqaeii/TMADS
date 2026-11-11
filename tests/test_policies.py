import pytest

from apps.campaigns.models import AdCreative, Campaign, CampaignTargeting
from apps.policies.constants import FindingSeverity, OperatorAuthorizationState
from apps.policies.models import OperatorAdvertisingAuthorization
from apps.policies.services.engine import evaluate_campaign
from apps.policies.services.preflight import CampaignPolicyPreflight, assert_submission_ready
from apps.policies.services.text_rules import check_ad_text, check_text_links


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
    CampaignTargeting.objects.create(campaign=campaign, config={"bot_ids": ["@b"]})
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
    CampaignTargeting.objects.create(campaign=campaign, config={"bot_ids": ["@b"]})
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
    CampaignTargeting.objects.create(campaign=campaign, config={"bot_ids": ["@b"]})
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
