"""UploadWebsitePhoto with private storage, explicit consent and bound receipt.

All remote writes remain disabled unless the existing independent operator,
paid-submission, website and media flags have been explicitly authorized.
"""
from hashlib import sha256
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.campaigns.models import Campaign
from apps.campaigns.media_validation import validate_website_photo
from apps.telegram_ads.models import APIRequestLog
from apps.telegram_ads.services.media import media_upload_enabled
from apps.telegram_ads.targeting.website import is_external
from apps.telegram_ads.services.account_connections import campaign_client
from apps.telegram_ads.exceptions import TelegramAdsError


def _signature(campaign, creative):
    if not creative or not creative.website_photo or not is_external(campaign.destination):
        return None
    f = creative.website_photo
    if not 0 < f.size <= 1024 * 1024 or Path(f.name).suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        return None
    try:
        digest = sha256()
        with f.open("rb") as stream:
            for chunk in iter(lambda: stream.read(65536), b""):
                digest.update(chunk)
    except (OSError, ValueError):
        return None
    return {
        "campaign_id": str(campaign.pk),
        "creative_id": str(creative.pk),
        "sha256": digest.hexdigest(),
        "account_scope": sha256(
            f"{campaign.telegram_connection_id}:{campaign.telegram_connection.remote_account_id}".encode()
            if campaign.telegram_connection_id else settings.TELEGRAM_ADS_API_TOKEN.encode()
        ).hexdigest(),
    }


def website_photo_enabled(campaign=None):
    return media_upload_enabled(campaign) and bool(getattr(settings, "TELEGRAM_ADS_WEBSITE_ENABLED", False))


def website_photo_receipt(campaign):
    if not website_photo_enabled(campaign):
        return None
    sig = _signature(campaign, campaign.creatives.first())
    if not sig:
        return None
    qs = APIRequestLog.objects.filter(operation="website_photo_upload", success=True)
    for key, value in sig.items():
        qs = qs.filter(**{"meta__" + key: value})
    record = qs.order_by("-created_at").first()
    photo_id = record.meta.get("photo_id") if record else None
    if not isinstance(photo_id, str) or not 0 < len(photo_id) <= 256:
        return None
    return photo_id


def upload_saved_website_photo(campaign, *, actor):
    """Persist a durable uncertain claim BEFORE external I/O; do not auto-retry."""
    profile = getattr(actor, "customer_profile", None)
    if not profile or profile.is_suspended:
        raise PermissionDenied
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk, customer=profile)
        from apps.campaigns.views import _campaign_editable
        if not _campaign_editable(campaign) or not website_photo_enabled(campaign):
            raise ValueError("بارگذاری تصویر وب‌سایت در این حساب مجاز نیست.")
        if not (campaign.ad_settings or {}).get("destination_rights_confirmed"):
            raise ValueError("حق استفاده از مقصد و تصویر را ابتدا تأیید و ذخیره کنید.")
        creative = campaign.creatives.first()
        sig = _signature(campaign, creative)
        if not sig:
            raise ValueError("تصویر وب‌سایت ذخیره نشده یا نامعتبر است.")
        if website_photo_receipt(campaign):
            return website_photo_receipt(campaign)
        if APIRequestLog.objects.filter(
            operation="website_photo_upload", meta__campaign_id=str(campaign.pk),
            meta__state="uncertain",
        ).exists():
            raise ValueError("نتیجه انتقال قبلی نامطمئن است؛ تطبیق لازم است.")
        with creative.website_photo.open("rb") as file:
            errors = validate_website_photo(file)
            if errors:
                raise ValueError("؛ ".join(errors))
        claim = APIRequestLog.objects.create(
            operation="website_photo_upload", success=False,
            meta={**sig, "state": "uncertain"},
        )

    # The claim has committed. A timeout cannot erase the evidence or permit
    # another upload by the same campaign without explicit reconciliation.
    try:
        with creative.website_photo.open("rb") as file:
            response = campaign_client(campaign).upload_website_photo(
                file, filename="site" + Path(creative.website_photo.name).suffix.lower(),
            )
        photo_id = response.get("photo_id") if isinstance(response, dict) else None
        if not isinstance(photo_id, str) or not 0 < len(photo_id) <= 256:
            raise ValueError("شناسه عکس معتبر نیست.")
        APIRequestLog.objects.filter(pk=claim.pk).update(
            success=True, meta={**sig, "photo_id": photo_id, "state": "completed"},
        )
        return photo_id
    except Exception as exc:
        raise TelegramAdsError(
            "نتیجه بارگذاری تصویر وب‌سایت نامطمئن است؛ ارسال مجدد تا تطبیق ممنوع است."
        ) from exc
