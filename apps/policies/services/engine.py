from __future__ import annotations

from apps.campaigns.models import Campaign
from apps.policies.constants import FindingSeverity, OperatorAuthorizationState
from apps.policies.models import OperatorAdvertisingAuthorization
from apps.policies.services.content_rules import scan_prohibited_hints
from apps.policies.services.destination_rules import check_destination_readiness
from apps.policies.services.financial_disclosures import budget_step_guidance
from apps.policies.services.policy_versions import get_active_policy_version
from apps.policies.services.rules_registry import rule_meta
from apps.policies.services.targeting_rules import check_targeting
from apps.policies.services.text_rules import check_ad_text, check_promote_url_format, check_text_links
from apps.policies.services.types import PolicyFindingDTO, PolicyRunResult


def _studio_validation_errors(campaign: Campaign, *, strict: bool) -> list[PolicyFindingDTO]:
    if not strict:
        return []
    from apps.telegram_ads.targeting.validators import validate_submission_ready

    vr = validate_submission_ready(campaign)
    findings: list[PolicyFindingDTO] = []
    for err in vr.errors:
        findings.append(
            PolicyFindingDTO(
                rule_id="GA-API-000",
                severity=FindingSeverity.BLOCKED,
                field_key="form",
                message_fa=err,
                source_document="GramAds API alignment",
                source_clause="createAd validation",
                source_url="",
            )
        )
    for warn in vr.warnings:
        findings.append(
            PolicyFindingDTO(
                rule_id="GA-API-000",
                severity=FindingSeverity.WARNING,
                field_key="form",
                message_fa=warn,
            )
        )
    if not findings and not vr.ok:
        findings.append(
            PolicyFindingDTO(
                rule_id="GA-API-000",
                severity=FindingSeverity.UNKNOWN,
                field_key="form",
                message_fa="اعتبارسنجی فنی کامل نیست.",
            )
        )
    return findings


def _operator_gate() -> PolicyFindingDTO | None:
    state = OperatorAdvertisingAuthorization.current_state()
    if state == OperatorAuthorizationState.APPROVED:
        return None
    meta = rule_meta("TG-TOS-006")
    if state == OperatorAuthorizationState.REJECTED:
        severity = FindingSeverity.BLOCKED
        message = "ارسال زندهٔ تبلیغ از طریق حساب مرکزی در وضعیت فعلی مجاز نیست (بررسی حقوقی)."
    else:
        severity = FindingSeverity.BLOCKED
        message = "مجوز ثبت تبلیغ مشتریان از طرف حساب مرکزی هنوز تأیید نشده است."
    return PolicyFindingDTO(
        rule_id="TG-TOS-006",
        severity=severity,
        field_key="operator",
        message_fa=message,
        source_document=meta.get("document", ""),
        source_clause=meta.get("clause", ""),
        source_url=meta.get("url", ""),
        requires_manual_review=True,
    )


def _terms_gate(campaign: Campaign, *, strict: bool) -> PolicyFindingDTO | None:
    settings = campaign.ad_settings or {}
    if settings.get("terms_accepted"):
        return None
    if not strict:
        return PolicyFindingDTO(
            rule_id="TMADS-ACC-001",
            severity=FindingSeverity.INFO,
            field_key="terms",
            message_fa="قبل از ثبت نهایی، شرایط گرام‌ادز و راهنمای تبلیغ را بپذیرید.",
            source_document="GramAds Terms",
            source_clause="Acceptance",
            source_url="/terms/",
        )
    return PolicyFindingDTO(
        rule_id="TMADS-ACC-001",
        severity=FindingSeverity.BLOCKED,
        field_key="terms",
        message_fa="پذیرش قوانین گرام‌ادز قبل از ثبت سفارش الزامی است.",
        source_document="GramAds Terms",
        source_clause="Acceptance",
        source_url="/terms/",
    )


def evaluate_campaign(
    campaign: Campaign,
    *,
    strict: bool = False,
    context: str = "wizard",
    include_budget_info: bool = False,
    check_operator: bool = False,
) -> PolicyRunResult:
    version = get_active_policy_version()
    creative = campaign.creatives.first()
    ad_text = creative.ad_text if creative else ""
    targeting = getattr(campaign, "targeting", None)
    config = targeting.config if targeting else {}

    allow_external = bool((campaign.ad_settings or {}).get("website_destination_allowed"))
    findings: list[PolicyFindingDTO] = []
    findings.extend(check_ad_text(campaign.target_type or "", ad_text))
    findings.extend(check_text_links(ad_text, campaign.destination))
    findings.extend(check_promote_url_format(campaign.destination, allow_external=allow_external))
    findings.extend(check_destination_readiness(campaign))
    findings.extend(check_targeting(campaign, config, ad_text=ad_text))
    findings.extend(scan_prohibited_hints(ad_text, title=campaign.name or ""))
    findings.extend(_studio_validation_errors(campaign, strict=strict))

    terms_f = _terms_gate(campaign, strict=strict)
    if terms_f:
        findings.append(terms_f)

    if check_operator:
        op = _operator_gate()
        if op:
            findings.append(op)

    if include_budget_info:
        findings.extend(budget_step_guidance())

    needs_review = any(
        f.severity == FindingSeverity.REVIEW_REQUIRED or f.requires_manual_review for f in findings
    )
    blocked = any(f.severity == FindingSeverity.BLOCKED for f in findings)
    submission_ready = not blocked
    if strict:
        submission_ready = submission_ready and not blocked

    return PolicyRunResult(
        findings=findings,
        policy_version_code=version.code,
        submission_ready=submission_ready,
        needs_manual_review=needs_review,
    )
