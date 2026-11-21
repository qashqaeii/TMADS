"""Telegram Ads write operations: local draft, dry-run, live (gated)."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from django.conf import settings

from apps.campaigns.models import Campaign, CampaignStatusHistory, TelegramAdvertisement
from apps.telegram_ads.services.account_connections import campaign_client
from apps.telegram_ads.exceptions import TelegramAdsError, TelegramAdsWriteDisabled
from apps.telegram_ads.models import APIRequestLog
from apps.telegram_ads.services.ad_payload import build_create_ad_payload, redact_payload_for_display
from apps.telegram_ads.targeting.validators import validate_submission_ready

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    LOCAL_DRAFT = "local_draft"
    DRY_RUN = "dry_run"
    LIVE = "live"


def dry_run_create_ad(campaign: Campaign) -> dict[str, Any]:
    """Validate and return the exact API payload without network write."""
    validation = validate_submission_ready(campaign)
    if not validation.ok:
        return {
            "ok": False,
            "mode": ExecutionMode.DRY_RUN.value,
            "errors": validation.errors,
            "warnings": validation.warnings,
        }
    payload = build_create_ad_payload(campaign, include_initial_budget=False)
    return {
        "ok": True,
        "mode": ExecutionMode.DRY_RUN.value,
        "api_method": "createAd",
        "payload": redact_payload_for_display(payload),
        "warnings": validation.warnings,
        "write_gates": {
            "TELEGRAM_ADS_WRITE_ENABLED": settings.TELEGRAM_ADS_WRITE_ENABLED,
            "TELEGRAM_ADS_PAID_SUBMISSION_ENABLED": settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED,
        },
    }


def execute_create_ad(
    campaign: Campaign,
    *,
    mode: ExecutionMode = ExecutionMode.LIVE,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    if mode == ExecutionMode.LOCAL_DRAFT:
        return {"ok": True, "mode": mode.value, "remote": False}

    dry = dry_run_create_ad(campaign)
    if not dry.get("ok"):
        raise ValueError("; ".join(dry.get("errors") or ["نامعتبر"]))

    order = None
    if mode == ExecutionMode.LIVE:
        if not settings.TELEGRAM_ADS_WRITE_ENABLED or not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
            raise TelegramAdsWriteDisabled("ارسال زنده غیرفعال است.")
        from apps.policies.services.preflight import assert_submission_ready
        from apps.telegram_ads.services.submission_guard import require_submission_order
        assert_submission_ready(campaign)
        order = require_submission_order(campaign, claimed=True)
    stable_key = f"tmads-create-{campaign.id}"
    if mode == ExecutionMode.LIVE and idempotency_key not in (None, stable_key):
        raise ValueError("کلید ایجاد تبلیغ باید ثابت باشد.")
    payload = build_create_ad_payload(
        campaign,
        include_initial_budget=True,
        idempotency_key=idempotency_key or stable_key,
        order=order,
    )

    if mode == ExecutionMode.DRY_RUN:
        APIRequestLog.objects.create(
            operation="create_ad_dry_run",
            success=True,
            meta={"campaign_id": str(campaign.id), "payload_keys": sorted(payload.keys())},
        )
        return {
            "ok": True,
            "mode": mode.value,
            "payload": redact_payload_for_display(payload),
        }

    if not settings.TELEGRAM_ADS_WRITE_ENABLED:
        raise TelegramAdsWriteDisabled("TELEGRAM_ADS_WRITE_ENABLED is false")
    if not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
        raise TelegramAdsWriteDisabled("TELEGRAM_ADS_PAID_SUBMISSION_ENABLED is false")

    client = campaign_client(campaign)
    try:
        result = client.create_advertisement(payload)
        APIRequestLog.objects.create(
            operation="create_ad",
            success=True,
            meta={"campaign_id": str(campaign.id), "idempotency_key": payload.get("idempotency_key")},
        )
    except Exception as exc:
        APIRequestLog.objects.create(
            operation="create_ad",
            success=False,
            meta={"campaign_id": str(campaign.id), "error": str(exc)[:300]},
        )
        raise

    remote_id = str(result.get("ad_id") or result.get("id") or "")
    if not remote_id.isdigit() or int(remote_id) <= 0:
        raise TelegramAdsError("تلگرام شناسه معتبر تبلیغ برنگرداند؛ تطبیق الزامی است.")
    ad, _ = TelegramAdvertisement.objects.get_or_create(campaign=campaign)
    ad.remote_ad_id = remote_id
    ad.remote_status = str(result.get("status") or "")
    ad.remote_status_raw = result
    ad.placement = campaign.placement
    ad.promotion_url = campaign.destination
    ad.save()
    APIRequestLog.objects.create(
        operation="create_ad_receipt", success=True,
        meta={"campaign_id": str(campaign.id), "order_id": str(order.id), "remote_ad_id": remote_id,
              "idempotency_key": stable_key},
    )
    return {"ok": True, "mode": mode.value, "result": result, "remote_ad_id": remote_id}
