from django.db import models


class FindingSeverity(models.TextChoices):
    BLOCKED = "blocked", "مسدود"
    REVIEW_REQUIRED = "review_required", "نیازمند بررسی"
    WARNING = "warning", "هشدار"
    INFO = "info", "راهنما"
    UNKNOWN = "unknown", "نامشخص"


class OperatorAuthorizationState(models.TextChoices):
    PENDING = "pending", "در انتظار بررسی حقوقی"
    APPROVED = "approved", "تأیید با مستندات"
    REJECTED = "rejected", "ممنوع"
    LEGAL_CLARIFICATION = "legal_clarification", "نیازمند توضیح حقوقی"


SOURCE_GUIDELINES = "https://ads.telegram.org/guidelines"
SOURCE_ADS_TOS = "https://ads.telegram.org/tos"
SOURCE_GETTING_STARTED = "https://ads.telegram.org/getting-started"
SOURCE_ADS_API = "https://ads.telegram.org/docs/api"
SOURCE_TELEGRAM_TOS = "https://telegram.org/tos"
SOURCE_TELEGRAM_PRIVACY = "https://telegram.org/privacy"

CURRENT_POLICY_VERSION = "2025-11-11-tmads-1"
TMADS_TERMS_VERSION = "tmads-legal-v1"
POLICY_SUMMARY_VERSION = "telegram-ads-guidelines-summary-1"
