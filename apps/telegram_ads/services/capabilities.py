from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError, TelegramAdsNotConfigured
from apps.telegram_ads.models import APICapability

logger = logging.getLogger(__name__)

READ_PROBES: tuple[tuple[str, str], ...] = (
    ("account.read", "get_current_account"),
    ("account.info", "get_account_info"),
    ("ads.list", "get_ads_list"),
    ("ads.get", "get_ads_list"),  # same permission tier
    ("ads.stats", "get_ad_stats"),
    ("ads.transactions", "get_ad_transactions_list"),
    ("targeting.languages", "get_target_languages_list"),
    ("targeting.topics", "get_target_topics_list"),
    ("targeting.countries", "get_target_countries_list"),
    ("targeting.bot", "get_target_bot"),
)

WRITE_FEATURES: tuple[tuple[str, str], ...] = (
    ("ads.create", "createAd"),
    ("ads.edit", "editAd"),
    ("ads.submit_review", "submitAdForReview"),
    ("ads.delete", "deleteAd"),
    ("media.upload_photo", "uploadAdPhoto"),
)


def _probe_read(client: TelegramAdsClient, method: str, *, sample_ad_id: int | None = None) -> tuple[str, dict]:
    with client._client() as c:
        if method == "get_current_account":
            c.get_current_account()
        elif method == "get_account_info":
            c.get_account_info()
        elif method == "get_ads_list":
            c.get_ads_list(limit=1)
        elif method == "get_ad_stats":
            if not sample_ad_id:
                return APICapability.State.UNVERIFIED, {"reason": "no_linked_ad_for_probe"}
            now = timezone.now()
            c.get_ad_stats(
                sample_ad_id,
                from_time=now - timedelta(days=3),
                to_time=now,
                interval=86400,
            )
        elif method == "get_ad_transactions_list":
            if not sample_ad_id:
                return APICapability.State.UNVERIFIED, {"reason": "no_linked_ad_for_probe"}
            c.get_ad_transactions_list(sample_ad_id, limit=1)
        elif method == "get_target_languages_list":
            c.get_target_languages_list()
        elif method == "get_target_topics_list":
            c.get_target_topics_list()
        elif method == "get_target_countries_list":
            c.get_target_countries_list()
        elif method == "get_target_bot":
            c.get_target_bot("HyperTunnelbot")
        else:
            return APICapability.State.UNVERIFIED, {"reason": f"unknown probe {method}"}
    return APICapability.State.SUPPORTED, {}


def refresh_api_capabilities(*, sample_ad_id: int | None = None) -> int:
    """Probe read-only API surface; store APICapability rows."""
    try:
        client = TelegramAdsClient()
    except TelegramAdsNotConfigured as exc:
        logger.warning("capabilities skip: %s", exc)
        return 0

    now = timezone.now()
    updated = 0

    for feature_key, method in READ_PROBES:
        state = APICapability.State.UNVERIFIED
        details: dict = {}
        try:
            state, details = _probe_read(client, method, sample_ad_id=sample_ad_id)
            if state == APICapability.State.UNVERIFIED and details.get("reason") == "no_linked_ad_for_probe":
                state = APICapability.State.TEMPORARY
        except TelegramAdsError as exc:
            state = APICapability.State.PERMISSION_DENIED
            details = {"error": exc.__class__.__name__, "message": str(exc)[:200]}
        except Exception as exc:  # noqa: BLE001
            state = APICapability.State.TEMPORARY
            details = {"error": str(exc)[:200]}

        APICapability.objects.update_or_create(
            feature_key=feature_key,
            defaults={"state": state, "details": details, "last_checked_at": now},
        )
        updated += 1

    for feature_key, api_method in WRITE_FEATURES:
        if not settings.TELEGRAM_ADS_WRITE_ENABLED:
            state = APICapability.State.UNSUPPORTED
            details = {"reason": "TELEGRAM_ADS_WRITE_ENABLED=false", "api_method": api_method}
        else:
            state = APICapability.State.UNVERIFIED
            details = {"reason": "write not probed in dry probe", "api_method": api_method}
        APICapability.objects.update_or_create(
            feature_key=feature_key,
            defaults={"state": state, "details": details, "last_checked_at": now},
        )
        updated += 1

    return updated
