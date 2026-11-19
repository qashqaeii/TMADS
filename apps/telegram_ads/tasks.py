import logging

from celery import shared_task

from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.sync import sync_ad_statistics_for, sync_remote_advertisements_readonly

from apps.campaigns.models import TelegramAdvertisement

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def task_sync_remote_ads(self):
    try:
        return sync_remote_advertisements_readonly()
    except TelegramAdsError as exc:
        logger.warning("sync_remote_ads failed: %s", exc)
        raise self.retry(exc=exc)


@shared_task
def task_emit_budget_alerts():
    from apps.notifications.budget_alerts import send_budget_alerts
    return send_budget_alerts()


@shared_task
def task_sync_active_ad_stats():
    count = 0
    for ad in TelegramAdvertisement.objects.exclude(remote_ad_id="").select_related("campaign"):
        if ad.campaign.status in {"active", "awaiting_telegram", "paused"}:
            try:
                sync_ad_statistics_for(ad)
                count += 1
            except TelegramAdsError:
                continue
    return count
