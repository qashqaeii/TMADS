from __future__ import annotations

from django.utils import timezone

from apps.policies.constants import CURRENT_POLICY_VERSION, SOURCE_GUIDELINES
from apps.policies.models import PolicyVersion


def get_active_policy_version() -> PolicyVersion:
    active = PolicyVersion.objects.filter(is_active=True).order_by("-effective_from").first()
    if active:
        return active
    today = timezone.localdate()
    return PolicyVersion.objects.get_or_create(
        code=CURRENT_POLICY_VERSION,
        defaults={
            "label_fa": "نسخه اولیه قوانین تبلیغ تلگرام (TMADS)",
            "guidelines_url": SOURCE_GUIDELINES,
            "effective_from": today,
            "is_active": True,
            "source_fingerprint": "guidelines-2025-11-11-fetch",
            "notes": "خلاصهٔ داخلی TMADS؛ متن رسمی تلگرام مرجع است.",
        },
    )[0]
