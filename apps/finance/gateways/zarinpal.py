from __future__ import annotations

import logging
import re

import httpx
from django.conf import settings

from .base import GatewayResult, PaymentGateway

logger = logging.getLogger(__name__)

ZARINPAL_API = "https://api.zarinpal.com/pg/v4/payment"
ZARINPAL_START = "https://www.zarinpal.com/pg/StartPay/{authority}"


class ZarinpalGateway(PaymentGateway):
    """Zarinpal v4: the request specifies IRR; verification uses the same amount."""

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
        if type(amount_irr) is not int or amount_irr <= 0:
            return GatewayResult(success=False, raw={"error": "invalid_amount"})
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_irr,
            "currency": "IRR",
            "callback_url": callback_url,
            "description": description[:255],
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{self._base}/request.json", json=payload)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
                    return GatewayResult(success=False, raw={"error": "invalid_gateway_response"})
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("zarinpal request failed: %s", type(exc).__name__)
            return GatewayResult(success=False, raw={"error": type(exc).__name__})

        authority = (data.get("data") or {}).get("authority")
        code = (data.get("data") or {}).get("code")
        if code == 100 and isinstance(authority, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", authority):
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
        if type(amount_irr) is not int or amount_irr <= 0:
            return GatewayResult(success=False, raw={"error": "invalid_amount"})
        if not isinstance(provider_reference, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", provider_reference):
            return GatewayResult(success=False, raw={"error": "invalid_authority"})
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount_irr,
            "authority": provider_reference,
        }
        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{self._base}/verify.json", json=payload)
                resp.raise_for_status()
                data = resp.json()
                if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
                    return GatewayResult(success=False, raw={"error": "invalid_gateway_response"})
        except (httpx.HTTPError, ValueError) as exc:
            return GatewayResult(success=False, raw={"error": type(exc).__name__})

        code = (data.get("data") or {}).get("code")
        if code in (100, 101):
            return GatewayResult(success=True, provider_reference=provider_reference, raw={"response": data})
        return GatewayResult(success=False, provider_reference=provider_reference, raw={"response": data})
