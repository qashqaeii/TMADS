from __future__ import annotations

import logging

import httpx
from django.conf import settings

from .base import GatewayResult, PaymentGateway

logger = logging.getLogger(__name__)

ZARINPAL_API = "https://api.zarinpal.com/pg/v4/payment"
ZARINPAL_START = "https://www.zarinpal.com/pg/StartPay/{authority}"


class ZarinpalGateway(PaymentGateway):
    """Zarinpal v4 request/verify. Amount is sent in Toman (IRR / 10)."""

    def __init__(self):
        self.merchant_id = settings.ZARINPAL_MERCHANT_ID
        self.sandbox = settings.ZARINPAL_SANDBOX

    @property
    def _base(self) -> str:
        if self.sandbox:
            return "https://sandbox.zarinpal.com/pg/v4/payment"
        return ZARINPAL_API

    @property
    def _start_url(self) -> str:
        if self.sandbox:
            return "https://sandbox.zarinpal.com/pg/StartPay/{authority}"
        return ZARINPAL_START

    def _configured(self) -> bool:
        return bool(self.merchant_id)

    def create_payment(self, *, amount_irr: int, callback_url: str, description: str) -> GatewayResult:
        if not self._configured():
            return GatewayResult(success=False, raw={"error": "ZARINPAL_MERCHANT_ID missing"})
        amount_toman = max(amount_irr // 10, 1)
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_toman,
            "callback_url": callback_url,
            "description": description[:255],
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{self._base}/request.json", json=payload)
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("zarinpal request failed: %s", exc)
            return GatewayResult(success=False, raw={"error": str(exc)})

        authority = (data.get("data") or {}).get("authority")
        code = (data.get("data") or {}).get("code")
        if code == 100 and authority:
            redirect_url = self._start_url.format(authority=authority)
            return GatewayResult(
                success=True,
                provider_reference=authority,
                raw={"redirect_url": redirect_url, "response": data},
            )
        return GatewayResult(success=False, raw={"response": data})

    def verify_payment(self, *, provider_reference: str, amount_irr: int) -> GatewayResult:
        if not self._configured():
            return GatewayResult(success=False, raw={"error": "ZARINPAL_MERCHANT_ID missing"})
        amount_toman = max(amount_irr // 10, 1)
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_toman,
            "authority": provider_reference,
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{self._base}/verify.json", json=payload)
                data = resp.json()
        except httpx.HTTPError as exc:
            return GatewayResult(success=False, raw={"error": str(exc)})

        code = (data.get("data") or {}).get("code")
        if code in (100, 101):
            return GatewayResult(success=True, provider_reference=provider_reference, raw={"response": data})
        return GatewayResult(success=False, provider_reference=provider_reference, raw={"response": data})
