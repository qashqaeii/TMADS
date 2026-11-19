from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import (
    TelegramAdsApiError, TelegramAdsError, TelegramAdsNotConfigured,
    TelegramAdsTransportError,
)
from apps.telegram_ads.models import APICapability

logger = logging.getLogger(__name__)

READ_PROBES: tuple[tuple[str, str], ...] = (
    ("account.read", "get_current_account"),
    ("account.info", "get_account_info"),
    ("account.related", "get_related_accounts_list"),
    ("account.transactions", "get_account_transactions_list"),
    ("account.stats", "get_account_stats"),
    ("account.report", "get_account_report"),
    ("audiences.list", "get_audiences_list"),
    ("pixel.events", "get_pixel_events_list"),
    ("pixel.read", "get_pixel"),
    ("ads.list", "get_ads_list"),
    ("ads.get", "get_ads_by_id"),
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
    ("media.upload_video", "uploadAdVideo"),
    ("media.website_photo", "uploadWebsitePhoto"),
    ("ads.budget_increase", "increaseAdBudget"),
    ("ads.budget_decrease", "decreaseAdBudget"),
    ("account.create", "createAccount"),
    ("account.budget_increase", "increaseAccountBudget"),
    ("account.budget_decrease", "decreaseAccountBudget"),
    ("audiences.create", "createAudience"),
    ("audiences.edit", "editAudience"),
    ("audiences.delete", "deleteAudience"),
    ("pixel.create", "createPixel"),
    ("pixel.event_create", "createPixelEvent"),
    ("pixel.event_edit", "editPixelEvent"),
    ("pixel.event_delete", "deletePixelEvent"),
)


def _probe_read(client: TelegramAdsClient, method: str, *, sample_ad_id: int | None = None) -> tuple[str, dict]:
    with client._client() as c:
        if method == "get_current_account":
            c.get_current_account()
        elif method == "get_account_info":
            c.get_account_info()
        elif method == "get_related_accounts_list":
            c.get_related_accounts_list(limit=1)
        elif method == "get_account_transactions_list":
            c.get_account_transactions_list(limit=1)
        elif method == "get_account_stats":
            now = timezone.now()
            c.get_account_stats(now-timedelta(days=3),now,86400)
        elif method == "get_account_report":
            now = timezone.now()
            c.get_account_report(now.year,now.month)
        elif method == "get_audiences_list":
            c.get_audiences_list(limit=1)
        elif method == "get_pixel":
            c.get_pixel()
        elif method == "get_pixel_events_list":
            c.get_pixel_events_list(limit=1)
        elif method == "get_ads_list":
            c.get_ads_list(limit=1)
        elif method == "get_ads_by_id":
            if not sample_ad_id:
                return APICapability.State.UNVERIFIED, {"reason": "no_linked_ad_for_probe"}
            c.get_ads_by_id([sample_ad_id])
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
            c.get_target_bot("@vote")
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
            # No sample is not a service outage or proof of denied permission.
        except TelegramAdsApiError as exc:
            api_code = str(exc.api_code or "").upper()
            denied = api_code in {"ACCESS_DENIED", "PERMISSION_DENIED", "TOKEN_INVALID", "TOKEN_EXPIRED", "AUTH_KEY_INVALID"}
            state = APICapability.State.PERMISSION_DENIED if denied else (
                APICapability.State.TEMPORARY if exc.retryable else APICapability.State.UNVERIFIED
            )
            details = {"error": api_code, "reason": "telegram_api_response"}
        except (TelegramAdsTransportError, TelegramAdsNotConfigured):
            state = APICapability.State.TEMPORARY
            details = {"reason": "network_or_configuration_unavailable"}
        except TelegramAdsError:
            state = APICapability.State.UNVERIFIED
            details = {"reason": "api_status_unverified"}
        except Exception as exc:  # noqa: BLE001
            state = APICapability.State.TEMPORARY
            details = {"error": type(exc).__name__, "reason": "probe_failed"}

        APICapability.objects.update_or_create(
            feature_key=feature_key,
            defaults={"state": state, "details": details, "last_checked_at": now},
        )
        updated += 1

    for feature_key, api_method in WRITE_FEATURES:
        if not settings.TELEGRAM_ADS_WRITE_ENABLED:
            state = APICapability.State.UNVERIFIED
            details = {"reason": "write_disabled_by_tmads_not_api_capability", "api_method": api_method}
        else:
            state = APICapability.State.UNVERIFIED
            details = {"reason": "write_not_probed_for_safety", "api_method": api_method}
        APICapability.objects.update_or_create(
            feature_key=feature_key,
            defaults={"state": state, "details": details, "last_checked_at": now},
        )
        updated += 1

    return updated
