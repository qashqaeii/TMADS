"""Upload only an explicitly selected private draft; keep account-bound proof."""
from hashlib import sha256
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.campaigns.models import Campaign
from apps.campaigns.media_validation import validate_telegram_creative_media
from apps.policies.services.preflight import CampaignPolicyPreflight
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.models import APIRequestLog


def media_upload_enabled():
    return bool(settings.TELEGRAM_ADS_WRITE_ENABLED and settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED
                and getattr(settings,"TELEGRAM_ADS_MEDIA_UPLOAD_ENABLED",False)
                and settings.TELEGRAM_ADS_API_TOKEN
                and CampaignPolicyPreflight.operator_submission_allowed())


def _signature(campaign, creative):
    if campaign.target_type not in {"channels","users"} or not creative or not creative.media:
        return None
    suffix=Path(creative.media.name).suffix.lower()
    if suffix not in {".jpg",".jpeg",".png",".mp4"}:
        return None
    try:
        max_size=20*1024*1024 if suffix==".mp4" else 5*1024*1024
        if not 0 < creative.media.size <= max_size:
            return None
        digest=sha256()
        with creative.media.open("rb") as f:
            size=0
            for chunk in iter(lambda:f.read(65536),b""):
                size+=len(chunk)
                if size>max_size:
                    return None
                digest.update(chunk)
        if not size:
            return None
    except (OSError,ValueError):
        return None
    return {"campaign_id":str(campaign.pk),"creative_id":str(creative.pk),
        "sha256":digest.hexdigest(),"account_scope":sha256(settings.TELEGRAM_ADS_API_TOKEN.encode()).hexdigest(),
        "field":"video_id" if suffix==".mp4" else "photo_id"}


def media_receipt(campaign):
    creative=campaign.creatives.first()
    if not creative or not creative.media or not media_upload_enabled():
        return None
    sig=_signature(campaign,creative)
    if not sig:
        return None
    qs=APIRequestLog.objects.filter(operation="media_upload_receipt",success=True)
    for k,v in sig.items():
        qs=qs.filter(**{"meta__"+k:v})
    row=qs.order_by("-created_at").first()
    media_id=row.meta.get("media_id") if row else None
    if isinstance(media_id,str) and media_id and len(media_id)<=256:
        return {"field":sig["field"],"media_id":media_id}
    return None


def upload_saved_media(campaign, *, actor):
    """Claim before network I/O; uncertain outcomes cannot trigger a second upload."""
    profile = getattr(actor, "customer_profile", None)
    if not profile or profile.is_suspended:
        raise PermissionDenied
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk, customer=profile)
        from apps.campaigns.views import _campaign_editable
        if not _campaign_editable(campaign) or not media_upload_enabled():
            raise ValueError("انتقال رسانه در وضعیت فعلی مجاز نیست.")
        if media_receipt(campaign):
            return media_receipt(campaign)
        creative = campaign.creatives.first()
        sig = _signature(campaign, creative)
        if not sig:
            raise ValueError("فایل ذخیره‌شده معتبر نیست.")
        if not (campaign.ad_settings or {}).get("destination_rights_confirmed"):
            raise ValueError("ابتدا حق استفاده از مقصد و رسانه را تأیید و ذخیره کنید.")
        if APIRequestLog.objects.filter(
                operation="media_upload_claim", meta__campaign_id=str(campaign.pk),
                meta__state="uncertain").exists():
            raise ValueError("نتیجه انتقال قبلی نامطمئن است؛ برای جلوگیری از تکرار باید تطبیق شود.")
        with creative.media.open("rb") as stream:
            errors = validate_telegram_creative_media(stream)
            if errors:
                raise ValueError("؛ ".join(errors))
        # This operation is never invoked under the wizard's outer transaction.
        APIRequestLog.objects.create(
            operation="media_upload_claim", success=False,
            meta={**sig, "state": "uncertain"},
        )

    try:
        with creative.media.open("rb") as stream:
            result = TelegramAdsClient().upload_creative_media(
                stream,
                filename="creative" + Path(creative.media.name).suffix.lower(),
                is_video=sig["field"] == "video_id",
            )
        media_id = result.get(sig["field"]) if isinstance(result, dict) else None
        if not isinstance(media_id, str) or not 0 < len(media_id) <= 256:
            raise ValueError("شناسه رسانه از تلگرام تأیید نشد.")
        # Bind confirmed receipt to both the account and exact content.
        with transaction.atomic():
            APIRequestLog.objects.create(
                operation="media_upload_receipt", success=True,
                meta={**sig, "media_id": media_id},
            )
            APIRequestLog.objects.filter(
                operation="media_upload_claim",
                meta__campaign_id=str(campaign.pk), meta__state="uncertain",
            ).update(success=True, meta={**sig, "state": "completed"})
        return {"field": sig["field"], "media_id": media_id}
    except Exception as exc:
        raise ValueError("نتیجه انتقال رسانه نامطمئن است؛ از درخواست مجدد تا تطبیق خودداری کنید.") from exc
