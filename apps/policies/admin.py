from django.contrib import admin

from apps.policies.models import (
    CampaignPolicyAcceptance,
    CampaignPolicyEvaluation,
    OperatorAdvertisingAuthorization,
    OpsPolicyReview,
    PolicyFinding,
    PolicyVersion,
)


@admin.register(PolicyVersion)
class PolicyVersionAdmin(admin.ModelAdmin):
    list_display = ("code", "effective_from", "is_active", "id")
    list_filter = ("is_active",)


class PolicyFindingInline(admin.TabularInline):
    model = PolicyFinding
    extra = 0
    readonly_fields = ("rule_id", "severity", "message_fa", "field_key")


@admin.register(CampaignPolicyEvaluation)
class CampaignPolicyEvaluationAdmin(admin.ModelAdmin):
    list_display = ("campaign", "policy_version", "run_at", "submission_ready", "blocked_count")
    inlines = [PolicyFindingInline]
    readonly_fields = ("run_at", "raw_snapshot")


@admin.register(OperatorAdvertisingAuthorization)
class OperatorAdvertisingAuthorizationAdmin(admin.ModelAdmin):
    list_display = ("state", "is_current", "reviewed_at", "id")
    list_filter = ("state", "is_current")


admin.site.register(CampaignPolicyAcceptance)
admin.site.register(OpsPolicyReview)
