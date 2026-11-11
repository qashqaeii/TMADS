from __future__ import annotations

import logging

from django.conf import settings

from apps.campaigns.models import Campaign, CampaignStatusHistory, TelegramAdvertisement
from apps.telegram_ads.exceptions import TelegramAdsWriteDisabled
from apps.telegram_ads.services.ad_write import ExecutionMode, execute_create_ad

logger = logging.getLogger(__name__)


def submit_campaign_to_telegram(campaign: Campaign) -> TelegramAdvertisement:
    """Submit approved campaign. Write gated by settings; never silent in production."""
    from apps.policies.services.preflight import assert_submission_ready

    assert_submission_ready(campaign)
    if not settings.TELEGRAM_ADS_WRITE_ENABLED:
        raise TelegramAdsWriteDisabled("TELEGRAM_ADS_WRITE_ENABLED is false")
    if not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
        raise TelegramAdsWriteDisabled("TELEGRAM_ADS_PAID_SUBMISSION_ENABLED is false")

    from apps.campaigns.studio import migrate_campaign_to_studio

    migrate_campaign_to_studio(campaign)
    creative = campaign.creatives.first()
    if campaign.target_type != "search" and (not creative or not (creative.ad_text or "").strip()):
        raise ValueError("متن تبلیغ کامل نیست.")
    if not campaign.destination:
        raise ValueError("مقصد تنظیم نشده است.")
    if not campaign.placement and campaign.target_type != "search":
        raise ValueError("جایگاه نمایش انتخاب نشده است.")

    campaign.status = Campaign.Status.SUBMITTING
    campaign.save(update_fields=["status", "updated_at"])

    try:
        execute_create_ad(campaign, mode=ExecutionMode.LIVE)
    except Exception:
        campaign.status = Campaign.Status.FAILED
        campaign.save(update_fields=["status", "updated_at"])
        raise

    campaign.status = Campaign.Status.AWAITING_TELEGRAM
    campaign.save(update_fields=["status", "updated_at"])
    CampaignStatusHistory.objects.create(
        campaign=campaign,
        to_status=campaign.status,
        note="ارسال به Telegram Ads",
    )
    return TelegramAdvertisement.objects.filter(campaign=campaign).first()
