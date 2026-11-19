from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable
from typing import Any

from django.conf import settings

from .exceptions import (
    TelegramAdsApiError,
    TelegramAdsError,
    TelegramAdsNotConfigured,
    TelegramAdsTransportError,
    TelegramAdsWriteDisabled,
)

logger = logging.getLogger(__name__)


def _humanize_api_error(exc: Exception) -> str:
    try:
        from telead.errors import TransportError

        if isinstance(exc, TransportError):
            return (
                "اتصال به سرور تبلیغات تلگرام برقرار نشد. "
                "اینترنت، پروکسی یا فیلترشکن را بررسی کنید و دوباره تلاش کنید."
            )
    except ImportError:
        pass
    text = str(exc)
    connection_hints = (
        "ConnectionRefusedError",
        "ConnectionError",
        "NewConnectionError",
        "Max retries exceeded",
        "Failed to establish",
        "promoteapi.telegram.org",
    )
    if type(exc).__name__ in ("ConnectionError", "ConnectionRefusedError") or any(h in text for h in connection_hints):
        return (
            "اتصال به سرور تبلیغات تلگرام برقرار نشد. "
            "اینترنت، پروکسی یا فیلترشکن را بررسی کنید و دوباره تلاش کنید."
        )
    return f"خطای API تبلیغات تلگرام: {exc}"


def _model_to_dict(obj: Any) -> dict[str, Any]:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    raw = getattr(obj, "raw", None)
    if isinstance(raw, dict) and raw:
        return dict(raw)
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if dataclasses.is_dataclass(obj):
        payload: dict[str, Any] = {}
        for field in dataclasses.fields(obj):
            if field.name == "raw":
                continue
            value = getattr(obj, field.name)
            if dataclasses.is_dataclass(value):
                value = _model_to_dict(value)
            elif isinstance(value, list):
                value = [_model_to_dict(v) if dataclasses.is_dataclass(v) else v for v in value]
            payload[field.name] = value
        return payload
    return {"value": str(obj)}


class TelegramAdsClient:
    """Wrapper around telead.Client with environment write gates."""

    def __init__(self, token: str | None = None):
        self.token = token or settings.TELEGRAM_ADS_API_TOKEN

    def _ensure_configured(self) -> None:
        if not self.token:
            raise TelegramAdsNotConfigured("TELEGRAM_ADS_API_TOKEN is not set")

    def _client(self):
        self._ensure_configured()
        try:
            from telead import Client
        except ImportError as exc:
            raise TelegramAdsNotConfigured("telead package not installed") from exc
        return Client(self.token)

    def _run(self, operation: str, fn: Callable[..., Any]) -> Any:
        with self._client() as client:
            try:
                return fn(client)
            except (TelegramAdsNotConfigured, TelegramAdsWriteDisabled, TelegramAdsError):
                raise
            except Exception as exc:
                try:
                    from telead.errors import APIError, TransportError

                    if isinstance(exc, APIError):
                        logger.info("Telegram Ads API %s error: %s", operation, exc)
                        raise TelegramAdsApiError(
                            exc.code,
                            description=exc.description,
                            method=exc.method,
                            retryable=getattr(exc, "retryable", False),
                        ) from exc
                    if isinstance(exc, TransportError):
                        logger.warning("Telegram Ads API %s transport failure", operation, exc_info=True)
                        raise TelegramAdsTransportError(_humanize_api_error(exc)) from exc
                except ImportError:
                    pass
                logger.warning("Telegram Ads API %s failed: %s", operation, exc, exc_info=True)
                raise TelegramAdsError(_humanize_api_error(exc)) from exc

    def get_account(self) -> dict[str, Any]:
        return self._run("get_account", lambda client: _model_to_dict(client.get_current_account()))

    def list_advertisements(self) -> list[dict[str, Any]]:
        def _list(client):
            items, seen, cursors = [], set(), set()
            offset = None
            for _ in range(1000):
                page = client.get_ads_list(offset=offset, limit=100)
                data = _model_to_dict(page)
                ads = data.get("ads")
                if not isinstance(ads, list):
                    raise TelegramAdsError("ساختار فهرست تبلیغات معتبر نیست.")
                for item in ads:
                    row = _model_to_dict(item)
                    ad_id = row.get("ad_id")
                    if type(ad_id) is not int or ad_id <= 0 or ad_id in seen:
                        raise TelegramAdsError("شناسه تکراری یا نامعتبر در صفحه‌بندی تبلیغات.")
                    seen.add(ad_id)
                    items.append(row)
                offset = data.get("next_offset")
                if not offset:
                    if type(data.get("total_count")) is int and data["total_count"] != len(items):
                        raise TelegramAdsError("تعداد تبلیغات هنگام دریافت تغییر کرده؛ دوباره تلاش کنید.")
                    return items
                if not isinstance(offset, str) or offset in cursors or not ads:
                    raise TelegramAdsError("صفحه‌بندی تبلیغات کامل نشد.")
                cursors.add(offset)
            raise TelegramAdsError("سقف امن صفحه‌بندی تبلیغات رسید؛ داده ناقص استفاده نشد.")

        return self._run("list_advertisements", _list)

    def get_account_info(self, *, account_id: str | None = None) -> dict[str, Any]:
        return self._run(
            "get_account_info",
            lambda client: _model_to_dict(client.get_account_info(account_id=account_id)),
        )

    def get_ad(self, ad_id: str, *, return_target: bool = False) -> dict[str, Any]:
        return self._run(
            "get_ad",
            lambda client: _model_to_dict(client.get_ad(int(ad_id), return_target=return_target)),
        )

    def get_ads_by_ids(self, ad_ids: list[int], *, return_target: bool = False) -> list[dict[str, Any]]:
        return self._run(
            "get_ads_by_ids",
            lambda client: [_model_to_dict(ad) for ad in client.get_ads_by_id(ad_ids, return_target=return_target)],
        )

    def get_ad_statistics(
        self,
        ad_id: str,
        *,
        from_time,
        to_time,
        interval: int = 86400,
    ) -> dict[str, Any]:
        def _stats(client):
            stats = client.get_ad_stats(
                ad_id=int(ad_id),
                from_time=from_time,
                to_time=to_time,
                interval=interval,
            )
            if isinstance(stats, list):
                return {"items": [_model_to_dict(s) for s in stats]}
            return _model_to_dict(stats)

        return self._run("get_ad_statistics", _stats)

    def get_ad_transactions(self, ad_id: str, *, limit: int = 20) -> dict[str, Any]:
        return self._run(
            "get_ad_transactions",
            lambda client: _model_to_dict(client.get_ad_transactions_list(int(ad_id), limit=limit)),
        )

    def get_target_languages(self) -> list[dict[str, Any]]:
        return self._run("get_target_languages", lambda client: [_model_to_dict(x) for x in client.get_target_languages_list()])

    def get_target_topics(self) -> list[dict[str, Any]]:
        return self._run("get_target_topics", lambda client: [_model_to_dict(x) for x in client.get_target_topics_list()])

    def get_target_countries(self) -> list[dict[str, Any]]:
        return self._run("get_target_countries", lambda client: [_model_to_dict(x) for x in client.get_target_countries_list()])

    def resolve_target_bot(self, bot: str) -> dict[str, Any]:
        return self._run("resolve_target_bot", lambda client: _model_to_dict(client.get_target_bot(bot)))

    def create_advertisement(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not settings.TELEGRAM_ADS_WRITE_ENABLED:
            raise TelegramAdsWriteDisabled("Write operations are disabled")
        if not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
            raise TelegramAdsWriteDisabled("Paid submission is disabled")
        return self._run("create_advertisement", lambda client: _model_to_dict(client.create_ad(**payload)))

    def edit_advertisement(self, ad_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not settings.TELEGRAM_ADS_WRITE_ENABLED:
            raise TelegramAdsWriteDisabled("Write operations are disabled")
        return self._run(
            "edit_advertisement",
            lambda client: _model_to_dict(client.edit_ad(ad_id=int(ad_id), **payload)),
        )

    def submit_ad_for_review(self, ad_id: str) -> dict[str, Any]:
        if not settings.TELEGRAM_ADS_WRITE_ENABLED:
            raise TelegramAdsWriteDisabled("Write operations are disabled")
        return self._run(
            "submit_ad_for_review",
            lambda client: _model_to_dict(client.submit_ad_for_review(ad_id=int(ad_id))),
        )

    def resolve_target_channel(self, channel: str | int, *, for_excluding=False) -> dict[str, Any]:
        return self._run("resolve_target_channel", lambda client: _model_to_dict(
            client.get_target_channel(channel, for_excluding=True) if for_excluding else client.get_target_channel(channel)))

    def get_target_locations_by_ids(self, location_ids: list[int]) -> list[dict[str, Any]]:
        return self._run("get_target_locations_by_id", lambda client: [
            _model_to_dict(item) for item in client.get_target_locations_by_id(location_ids=location_ids)
        ])

    def get_target_locations(self, country_code: str, query: str, *, limit: int = 20) -> dict[str, Any]:
        return self._run(
            "get_target_locations",
            lambda client: _model_to_dict(
                client.get_target_locations_list(country_code=country_code, query=query, limit=limit)
            ),
        )


    def upload_creative_media(self, file, *, filename: str, is_video: bool):
        if not (settings.TELEGRAM_ADS_WRITE_ENABLED and settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED
                and getattr(settings, "TELEGRAM_ADS_MEDIA_UPLOAD_ENABLED", False)):
            raise TelegramAdsWriteDisabled("Media upload is disabled")
        if is_video:
            return self._run("upload_ad_video", lambda client: _model_to_dict(client.upload_ad_video(file, filename=filename)))
        return self._run("upload_ad_photo", lambda client: _model_to_dict(client.upload_ad_photo(file, filename=filename)))


    def get_related_accounts(self, *, offset=0, limit=50):
        return self._run("related_accounts", lambda c: _model_to_dict(c.get_related_accounts_list(offset=offset,limit=limit)))

    def get_account_transactions(self, *, offset=None, limit=50):
        return self._run("account_transactions", lambda c: _model_to_dict(c.get_account_transactions_list(offset=offset,limit=limit)))

    def get_transaction_status(self, transaction_id):
        return self._run("account_transaction_status", lambda c: _model_to_dict(c.get_transaction_status(transaction_id)))

    def get_account_report(self, year, month):
        return self._run("account_report", lambda c: [_model_to_dict(x) for x in c.get_account_report(year,month)])

    def get_account_statistics(self, *, from_time, to_time, interval=86400):
        return self._run("account_stats", lambda c: [_model_to_dict(x) for x in c.get_account_stats(from_time,to_time,interval)])

    def get_audiences(self, *, offset=0, limit=50):
        return self._run("audiences_list", lambda c: _model_to_dict(c.get_audiences_list(offset=offset,limit=limit)))

    def get_pixel_info(self):
        return self._run("pixel_info", lambda c: _model_to_dict(c.get_pixel()))

    def get_pixel_events(self, *, offset=0, limit=50):
        return self._run("pixel_events", lambda c: _model_to_dict(c.get_pixel_events_list(offset=offset,limit=limit)))


    def create_related_account(self, *, title, details, idempotency_key):
        if not (settings.TELEGRAM_ADS_WRITE_ENABLED and settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED
                and getattr(settings,"TELEGRAM_ADS_RELATED_ACCOUNTS_ENABLED",False)):
            raise TelegramAdsWriteDisabled("Related account provisioning is disabled")
        return self._run("related_account_create",lambda c:_model_to_dict(c.create_account(title,**details,idempotency_key=idempotency_key)))
