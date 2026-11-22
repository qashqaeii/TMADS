from django.conf import settings
from django.db import models

from apps.campaigns.models import Campaign
from apps.core.models import UUIDModel
from apps.policies.constants import FindingSeverity, OperatorAuthorizationState


class PolicyVersion(UUIDModel):
    """Internal snapshot of rule set; official Telegram texts remain authoritative."""

    code = models.CharField(max_length=64, unique=True, db_index=True)
    label_fa = models.CharField(max_length=200)
    guidelines_url = models.URLField(default="https://ads.telegram.org/guidelines")
    ads_tos_url = models.URLField(default="https://ads.telegram.org/tos")
    effective_from = models.DateField()
    is_active = models.BooleanField(default=False, db_index=True)
    source_fingerprint = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_policy_versions",
    )

    class Meta:
        ordering = ["-effective_from", "-id"]

    def __str__(self) -> str:
        return self.code


class CampaignPolicyEvaluation(UUIDModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="policy_evaluations")
    policy_version = models.ForeignKey(
        PolicyVersion,
        on_delete=models.PROTECT,
        related_name="evaluations",
    )
    run_at = models.DateTimeField(auto_now_add=True)
    context_trigger = models.CharField(max_length=64, blank=True)
    blocked_count = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    info_count = models.PositiveIntegerField(default=0)
    submission_ready = models.BooleanField(default=False)
    summary_fa = models.CharField(max_length=500, blank=True)
    raw_snapshot = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-run_at"]


class PolicyFinding(UUIDModel):
    evaluation = models.ForeignKey(
        CampaignPolicyEvaluation,
        on_delete=models.CASCADE,
        related_name="findings",
    )
    rule_id = models.CharField(max_length=64, db_index=True)
    severity = models.CharField(max_length=24, choices=FindingSeverity.choices)
    message_fa = models.CharField(max_length=500)
    suggestion_fa = models.CharField(max_length=500, blank=True)
    field_key = models.CharField(max_length=64, blank=True)
    source_document = models.CharField(max_length=120, blank=True)
    source_clause = models.CharField(max_length=120, blank=True)
    source_url = models.URLField(blank=True)
    requires_manual_review = models.BooleanField(default=False)

    class Meta:
        ordering = ["severity", "rule_id"]


class CampaignPolicyAcceptance(UUIDModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="policy_acceptances")
    customer = models.ForeignKey(
        "accounts.CustomerProfile",
        on_delete=models.CASCADE,
        related_name="policy_acceptances",
    )
    tmads_terms_version = models.CharField(max_length=64)
    policy_summary_version = models.CharField(max_length=64)
    policy_version = models.ForeignKey(
        PolicyVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    acceptance_text_fa = models.TextField(blank=True)

    class Meta:
        ordering = ["-accepted_at"]


class OperatorAdvertisingAuthorization(UUIDModel):
    """Commercial launch gate — third-party bidding on central account (Ads TOS 3.3(e))."""

    state = models.CharField(
        max_length=32,
        choices=OperatorAuthorizationState.choices,
        default=OperatorAuthorizationState.PENDING,
    )
    documented_basis = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operator_ad_auth_reviews",
    )
    internal_notes = models.TextField(blank=True)
    is_current = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-reviewed_at", "-id"]

    @classmethod
    def current_state(cls) -> str:
        row = cls.objects.filter(is_current=True).order_by("-id").first()
        if row:
            return row.state
        return OperatorAuthorizationState.PENDING


class OpsPolicyReview(UUIDModel):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="ops_policy_reviews")
    evaluation = models.ForeignKey(
        CampaignPolicyEvaluation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ops_reviews",
    )
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    decision = models.CharField(max_length=32)
    reason_customer_fa = models.TextField()
    reason_internal = models.TextField(blank=True)
    policy_version_code = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
