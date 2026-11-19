from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction

from apps.campaigns.models import Campaign, CampaignStatusHistory, TelegramAdvertisement
from apps.finance.models import AdvertisingOrder
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError, TelegramAdsWriteDisabled
from apps.telegram_ads.services.ad_write import ExecutionMode, execute_create_ad
from apps.telegram_ads.services.submission_guard import require_submission_order

logger = logging.getLogger(__name__)


def _claim_submission(campaign_id):
    from apps.policies.services.preflight import assert_submission_ready

    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign_id)
        order = require_submission_order(campaign, lock=True)
        from apps.operations.review import require_recorded_approval
        require_recorded_approval(campaign)
        assert_submission_ready(campaign)
        if campaign.target_type == Campaign.TargetType.BOTS:
            from apps.telegram_ads.services.bot_eligibility import validate_bot_targets
            targeting = getattr(campaign, "targeting", None)
            bot_ids = (targeting.config if targeting else {}).get("bot_ids") or []
            errors = validate_bot_targets(bot_ids, strict=True, require_verified=True)
            if errors or not bot_ids:
                raise ValueError("؛ ".join(errors) or "ربات هدف تأیید نشده است.")
        account = TelegramAdsClient().get_account()
        try:
            remaining = Decimal(str(account["remaining_budget"]))
            if account.get("currency") != "TON" or not remaining.is_finite() or remaining < order.ton_allocation:
                raise ValueError("ارز یا موجودی حساب مرکزی برای سفارش معتبر نیست.")
        except (InvalidOperation, TypeError, KeyError):
            raise ValueError("موجودی حساب مرکزی قابل تأیید نیست.") from None
        campaign.status = Campaign.Status.SUBMITTING
        campaign.save(update_fields=["status", "updated_at"])
        order.status = AdvertisingOrder.Status.SUBMITTING
        order.save(update_fields=["status", "updated_at"])
        CampaignStatusHistory.objects.create(
            campaign=campaign, from_status=Campaign.Status.READY_FOR_SUBMISSION,
            to_status=campaign.status, note="ارسال در جریان؛ کلید یکتای ثابت",
        )
        return campaign, order.id


def submit_campaign_to_telegram(campaign: Campaign) -> TelegramAdvertisement:
    """Claim before external I/O; ambiguous outcomes must be reconciled, never blindly retried."""
    if not settings.TELEGRAM_ADS_WRITE_ENABLED or not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
        raise TelegramAdsWriteDisabled("ارسال زنده غیرفعال است.")
    campaign, order_id = _claim_submission(campaign.pk)
    try:
        execute_create_ad(campaign, mode=ExecutionMode.LIVE)
        with transaction.atomic():
            current = Campaign.objects.select_for_update().get(pk=campaign.pk)
            order = AdvertisingOrder.objects.select_for_update().get(pk=order_id)
            ad = TelegramAdvertisement.objects.get(campaign=current)
            if not ad.remote_ad_id:
                raise TelegramAdsError("شناسه تبلیغ برای تطبیق موجود نیست.")
            current.status = Campaign.Status.AWAITING_TELEGRAM
            current.save(update_fields=["status", "updated_at"])
            # Keep the reservation until a separately verified settlement is recorded.
            order.status = AdvertisingOrder.Status.SUBMITTING
            order.save(update_fields=["status", "updated_at"])
            CampaignStatusHistory.objects.create(
                campaign=current, from_status=Campaign.Status.SUBMITTING,
                to_status=current.status, note="شناسه تبلیغ از تلگرام دریافت شد؛ تسویه مالی در انتظار تطبیق",
            )
            return ad
    except Exception as exc:
        logger.warning("submission requires reconciliation for campaign=%s (%s)", campaign.pk, type(exc).__name__)
        with transaction.atomic():
            current = Campaign.objects.select_for_update().get(pk=campaign.pk)
            current.status = Campaign.Status.RECONCILIATION
            current.save(update_fields=["status", "updated_at"])
            CampaignStatusHistory.objects.create(
                campaign=current, from_status=Campaign.Status.SUBMITTING,
                to_status=current.status, note="نتیجه ارسال نامطمئن؛ ارسال مجدد ممنوع تا تطبیق",
            )
        raise TelegramAdsError("نتیجه ارسال نیازمند تطبیق است. برای جلوگیری از ایجاد تبلیغ تکراری، دوباره ارسال نکنید.") from exc
