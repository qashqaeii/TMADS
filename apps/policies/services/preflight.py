from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.campaigns.models import Campaign
from apps.policies.constants import (
    POLICY_SUMMARY_VERSION,
    TMADS_TERMS_VERSION,
    FindingSeverity,
    OperatorAuthorizationState,
)
from apps.policies.models import (
    CampaignPolicyAcceptance,
    CampaignPolicyEvaluation,
    OperatorAdvertisingAuthorization,
    PolicyFinding,
)
from apps.policies.services.engine import evaluate_campaign
from apps.policies.services.policy_versions import get_active_policy_version
from apps.policies.services.types import PolicyRunResult


class CampaignPolicyPreflight:
    """Authoritative policy pass before internal approval or Telegram submission."""

    def __init__(self, campaign: Campaign, *, actor=None):
        self.campaign = campaign
        self.actor = actor

    def run(
        self,
        *,
        strict: bool = True,
        persist: bool = True,
        context: str = "preflight",
        check_operator: bool = True,
    ) -> PolicyRunResult:
        customer = self.campaign.customer
        if customer is None:
            raise ValueError("کمپین بدون مالک معتبر است.")

        result = evaluate_campaign(
            self.campaign,
            strict=strict,
            context=context,
            check_operator=check_operator,
        )
        if not persist:
            return result

        version = get_active_policy_version()
        counts = result.counts()
        with transaction.atomic():
            evaluation = CampaignPolicyEvaluation.objects.create(
                campaign=self.campaign,
                policy_version=version,
                context_trigger=context,
                blocked_count=counts.get(FindingSeverity.BLOCKED, 0),
                review_count=counts.get(FindingSeverity.REVIEW_REQUIRED, 0),
                warning_count=counts.get(FindingSeverity.WARNING, 0),
                info_count=counts.get(FindingSeverity.INFO, 0),
                submission_ready=result.submission_ready,
                summary_fa=_summary_fa(counts),
                raw_snapshot=_snapshot(self.campaign),
            )
            PolicyFinding.objects.bulk_create(
                [
                    PolicyFinding(
                        evaluation=evaluation,
                        rule_id=f.rule_id,
                        severity=f.severity,
                        message_fa=f.message_fa[:500],
                        suggestion_fa=f.suggestion_fa[:500],
                        field_key=f.field_key,
                        source_document=f.source_document,
                        source_clause=f.source_clause,
                        source_url=f.source_url[:200],
                        requires_manual_review=f.requires_manual_review,
                    )
                    for f in result.findings
                ]
            )
            result.evaluation_id = str(evaluation.id)
        return result

    @staticmethod
    def operator_submission_allowed() -> bool:
        return OperatorAdvertisingAuthorization.current_state() == OperatorAuthorizationState.APPROVED

    @staticmethod
    def record_acceptance(
        campaign: Campaign,
        *,
        request=None,
        acceptance_text: str = "",
    ) -> CampaignPolicyAcceptance:
        version = get_active_policy_version()
        ip = None
        ua = ""
        if request is not None:
            ip = request.META.get("REMOTE_ADDR")
            ua = (request.META.get("HTTP_USER_AGENT") or "")[:255]
        return CampaignPolicyAcceptance.objects.create(
            campaign=campaign,
            customer=campaign.customer,
            tmads_terms_version=TMADS_TERMS_VERSION,
            policy_summary_version=POLICY_SUMMARY_VERSION,
            policy_version=version,
            ip_address=ip,
            user_agent=ua,
            acceptance_text_fa=acceptance_text,
        )

    @staticmethod
    def latest_evaluation(campaign: Campaign) -> CampaignPolicyEvaluation | None:
        return campaign.policy_evaluations.select_related("policy_version").first()


def assert_submission_ready(campaign: Campaign, *, check_operator: bool = True) -> PolicyRunResult:
    if check_operator and not CampaignPolicyPreflight.operator_submission_allowed():
        result = evaluate_campaign(campaign, strict=True, check_operator=True)
        if not result.submission_ready:
            blocked = [f.message_fa for f in result.findings if f.severity == FindingSeverity.BLOCKED]
            raise ValueError(blocked[0] if blocked else "ارسال تبلیغ مجاز نیست.")
    preflight = CampaignPolicyPreflight(campaign).run(strict=True, context="telegram_submit", check_operator=check_operator)
    if not preflight.submission_ready or preflight.blocked:
        msgs = [f.message_fa for f in preflight.findings if f.severity == FindingSeverity.BLOCKED]
        raise ValueError("; ".join(msgs) if msgs else "پیش‌پرواز سیاست رد شد.")
    return preflight


def _summary_fa(counts: dict[str, int]) -> str:
    ok = max(0, 5 - counts.get(FindingSeverity.BLOCKED, 0) - counts.get(FindingSeverity.REVIEW_REQUIRED, 0))
    return (
        f"{ok} بررسی بدون مانع — "
        f"{counts.get(FindingSeverity.BLOCKED, 0)} مسدود، "
        f"{counts.get(FindingSeverity.REVIEW_REQUIRED, 0)} نیازمند بررسی"
    )


def _snapshot(campaign: Campaign) -> dict[str, Any]:
    creative = campaign.creatives.first()
    targeting = getattr(campaign, "targeting", None)
    return {
        "target_type": campaign.target_type,
        "placement": campaign.placement,
        "destination": campaign.destination,
        "ad_text_len": len((creative.ad_text if creative else "") or ""),
        "targeting_keys": list((targeting.config if targeting else {}).keys()),
        "status": campaign.status,
    }
