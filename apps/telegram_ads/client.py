from __future__ import annotations

import dataclasses
import logging
from typing import Any

from django.conf import settings

from .exceptions import TelegramAdsError, TelegramAdsNotConfigured, TelegramAdsWriteDisabled

logger = logging.getLogger(__name__)


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

    def get_account(self) -> dict[str, Any]:
        with self._client() as client:
            account = client.get_current_account()
            return _model_to_dict(account)

    def list_advertisements(self) -> list[dict[str, Any]]:
        with self._client() as client:
            ads_list = client.get_ads_list()
            items = getattr(ads_list, "ads", None) or getattr(ads_list, "items", None) or []
            return [_model_to_dict(ad) for ad in items]

    def get_account_info(self, *, account_id: str | None = None) -> dict[str, Any]:
        with self._client() as client:
            return _model_to_dict(client.get_account_info(account_id=account_id))

    def get_ad(self, ad_id: str, *, return_target: bool = False) -> dict[str, Any]:
        with self._client() as client:
            ad = client.get_ad(int(ad_id), return_target=return_target)
            return _model_to_dict(ad)

    def get_ads_by_ids(self, ad_ids: list[int], *, return_target: bool = False) -> list[dict[str, Any]]:
        with self._client() as client:
            ads = client.get_ads_by_id(ad_ids, return_target=return_target)
            return [_model_to_dict(ad) for ad in ads]

    def get_ad_statistics(
        self,
        ad_id: str,
        *,
        from_time,
        to_time,
        interval: int = 86400,
    ) -> dict[str, Any]:
        with self._client() as client:
            stats = client.get_ad_stats(
                ad_id=int(ad_id),
                from_time=from_time,
                to_time=to_time,
                interval=interval,
            )
            if isinstance(stats, list):
                return {"items": [_model_to_dict(s) for s in stats]}
            return _model_to_dict(stats)

    def get_ad_transactions(self, ad_id: str, *, limit: int = 20) -> dict[str, Any]:
        with self._client() as client:
            tx = client.get_ad_transactions_list(int(ad_id), limit=limit)
            return _model_to_dict(tx)

    def get_target_languages(self) -> list[dict[str, Any]]:
        with self._client() as client:
            return [_model_to_dict(x) for x in client.get_target_languages_list()]

    def get_target_topics(self) -> list[dict[str, Any]]:
        with self._client() as client:
            return [_model_to_dict(x) for x in client.get_target_topics_list()]

    def get_target_countries(self) -> list[dict[str, Any]]:
        with self._client() as client:
            return [_model_to_dict(x) for x in client.get_target_countries_list()]

    def resolve_target_bot(self, bot: str) -> dict[str, Any]:
        with self._client() as client:
            return _model_to_dict(client.get_target_bot(bot))

    def create_advertisement(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not settings.TELEGRAM_ADS_WRITE_ENABLED:
            raise TelegramAdsWriteDisabled("Write operations are disabled")
        if not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
            raise TelegramAdsWriteDisabled("Paid submission is disabled")
        with self._client() as client:
            ad = client.create_ad(**payload)
            return _model_to_dict(ad)

    def edit_advertisement(self, ad_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not settings.TELEGRAM_ADS_WRITE_ENABLED:
            raise TelegramAdsWriteDisabled("Write operations are disabled")
        with self._client() as client:
            ad = client.edit_ad(ad_id=int(ad_id), **payload)
            return _model_to_dict(ad)

    def submit_ad_for_review(self, ad_id: str) -> dict[str, Any]:
        if not settings.TELEGRAM_ADS_WRITE_ENABLED:
            raise TelegramAdsWriteDisabled("Write operations are disabled")
        with self._client() as client:
            ad = client.submit_ad_for_review(ad_id=int(ad_id))
            return _model_to_dict(ad)

    def resolve_target_channel(self, channel: str) -> dict[str, Any]:
        with self._client() as client:
            return _model_to_dict(client.get_target_channel(channel))

    def get_target_locations(self, country_code: str, query: str, *, limit: int = 20) -> dict[str, Any]:
        with self._client() as client:
            return _model_to_dict(client.get_target_locations_list(country_code=country_code, query=query, limit=limit))
