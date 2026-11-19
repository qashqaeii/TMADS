"""Zibal IPG adapter. All amounts are integer IRR; callback data is never proof."""
from __future__ import annotations

import re
import httpx
from django.conf import settings
from .base import GatewayResult, PaymentGateway

API = "https://gateway.zibal.ir/v1"
START = "https://gateway.zibal.ir/start/"


def track_id(value):
    value = str(value or "")
    return value if re.fullmatch(r"[0-9]{1,32}", value) and int(value) > 0 else ""


def exact_integer(value):
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,19}", value):
        return int(value)
    return None


class ZibalGateway(PaymentGateway):
    def __init__(self):
        self.merchant = settings.ZIBAL_MERCHANT_ID.strip()

    def _configured(self):
        return bool(self.merchant) and not (
            settings.APP_ENV.upper() == "PRODUCTION" and self.merchant.lower() == "zibal"
        )

    def _post(self, endpoint, payload):
        if not self._configured():
            return {"error": "merchant_not_configured"}
        try:
            with httpx.Client(timeout=15.0, follow_redirects=False) as client:
                response = client.post(f"{API}/{endpoint}", json={"merchant": self.merchant, **payload})
                response.raise_for_status()
                data = response.json()
            return data if isinstance(data, dict) else {"error": "invalid_response"}
        except (httpx.HTTPError, ValueError):
            return {"error": "gateway_unavailable"}

    def create_payment(self, *, amount_irr, callback_url, description):
        if type(amount_irr) is not int or amount_irr < 10000:
            return GatewayResult(False, raw={"error": "invalid_amount"})
        payload = {"amount": amount_irr, "callbackUrl": callback_url,
                   "description": description[:255]}
        if description.startswith("topup-"):
            payload["orderId"] = description[6:]
        data = self._post("request", payload)
        code = exact_integer(data.get("result"))
        ref = track_id(data.get("trackId"))
        if code == 100 and ref:
            return GatewayResult(True, ref, {"code": code, "redirect_url": START + ref})
        return GatewayResult(False, raw={"code": code, "error": data.get("error", "request_rejected")})

    def verify_payment(self, *, provider_reference, amount_irr):
        ref = track_id(provider_reference)
        if not ref or type(amount_irr) is not int or amount_irr <= 0:
            return GatewayResult(False, raw={"error": "invalid_reference_or_amount"})
        data = self._post("verify", {"trackId": int(ref)})
        code = exact_integer(data.get("result"))
        # Already-verified responses may omit settlement fields. Obtain authenticated
        # inquiry evidence before crediting a locally unfinished payment.
        if code == 201 and (exact_integer(data.get("amount")) is None or not data.get("refNumber")):
            inquiry = self._post("inquiry", {"trackId": int(ref)})
            if exact_integer(inquiry.get("result")) != 100 or exact_integer(inquiry.get("status")) != 1:
                return GatewayResult(False, ref, {"code": code, "error": "inquiry_not_confirmed"})
            data = inquiry
        paid = exact_integer(data.get("amount"))
        bank_ref = str(data.get("refNumber") or "")
        if not re.fullmatch(r"[0-9A-Za-z_-]{1,128}", bank_ref):
            bank_ref = ""
        audit = {"code": code, "paid_amount_irr": paid, "bank_reference": bank_ref}
        if code not in (100, 201):
            return GatewayResult(False, ref, {**audit, "error": data.get("error", "not_verified")})
        if paid != amount_irr or not bank_ref:
            return GatewayResult(False, ref, {**audit, "error": "amount_or_receipt_mismatch"})
        if data.get("trackId") is not None and track_id(data.get("trackId")) != ref:
            return GatewayResult(False, ref, {**audit, "error": "reference_mismatch"})
        return GatewayResult(True, ref, audit)
