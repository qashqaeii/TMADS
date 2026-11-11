import logging

from celery import shared_task

from apps.finance.exceptions import NobitexAPIError, InvalidRateError
from apps.finance.services.ton_exchange_rate import fetch_live_snapshot

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def refresh_ton_exchange_rate(self):
    try:
        snap = fetch_live_snapshot(persist=True)
        return {
            "irr_per_ton": snap.irr_per_ton,
            "market": snap.market_symbol,
            "fetched_at": snap.fetched_at.isoformat(),
        }
    except (NobitexAPIError, InvalidRateError) as exc:
        logger.warning("refresh_ton_exchange_rate failed: %s", exc)
        raise
