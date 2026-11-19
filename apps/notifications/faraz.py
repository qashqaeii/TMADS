"""FarazSMS REST v1, based on Divarfiling and official Iranpayamak contract."""
from dataclasses import dataclass
import re

import httpx
from django.conf import settings

BASE = "https://api.iranpayamak.com"
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize_mobile(raw):
    phone = re.sub(r"[\s()-]", "", str(raw or "").translate(DIGITS))
    if phone.startswith("+98"):
        phone = "0" + phone[3:]
    elif phone.startswith("0098"):
        phone = "0" + phone[4:]
    elif phone.startswith("98"):
        phone = "0" + phone[2:]
    return phone if re.fullmatch(r"09[0-9]{9}", phone) else ""


@dataclass(frozen=True)
class SmsResult:
    state: str
    provider_id: str = ""
    error: str = ""


def configured(purpose):
    if not settings.SMS_ENABLED:
        return False
    if settings.SMS_PROVIDER == "console":
        return settings.APP_ENV.upper() != "PRODUCTION"
    line = (settings.FARAZSMS_OTP_LINE_NUMBER or settings.FARAZSMS_LINE_NUMBER
            if purpose == "verify_mobile" else settings.FARAZSMS_LINE_NUMBER)
    return bool(settings.SMS_PROVIDER == "faraz" and settings.FARAZSMS_API_KEY.strip()
                and line.strip() and settings.FARAZSMS_PATTERNS.get(purpose, "").strip())


def request(method, path, body=None):
    if not settings.FARAZSMS_API_KEY.strip():
        return None, "configuration_missing"
    try:
        with httpx.Client(timeout=12.0, follow_redirects=False) as client:
            response = client.request(method, BASE + path,
                headers={"Api-Key": settings.FARAZSMS_API_KEY.strip(), "Accept": "application/json"},
                **({"json": body} if body is not None else {}))
        if response.status_code in (401, 403):
            return None, "auth_failed"
        if 400 <= response.status_code < 500:
            return None, "provider_rejected"
        if not 200 <= response.status_code < 300:
            return None, "outcome_unknown"
        data = response.json()
        if not isinstance(data, dict):
            return None, "outcome_unknown"
        if data.get("status") == "error":
            return None, "provider_rejected"
        if data.get("status") != "success":
            return None, "outcome_unknown"
        return data.get("data"), ""
    except (httpx.HTTPError, ValueError):
        # No blind retries: a timeout may have transmitted the SMS.
        return None, "outcome_unknown"


def send_pattern(phone, purpose, attributes):
    phone = normalize_mobile(phone)
    if not phone:
        return SmsResult("failed", error="invalid_phone")
    if not configured(purpose):
        return SmsResult("failed", error="configuration_missing")
    if settings.SMS_PROVIDER == "console":
        return SmsResult("simulated")
    line = (settings.FARAZSMS_OTP_LINE_NUMBER or settings.FARAZSMS_LINE_NUMBER
            if purpose == "verify_mobile" else settings.FARAZSMS_LINE_NUMBER)
    data, error = request("POST", "/ws/v1/sms/pattern", {
        "code": settings.FARAZSMS_PATTERNS[purpose].strip(), "recipient": phone,
        "attributes": {str(k): str(v) for k, v in attributes.items()},
        "line_number": line.strip(), "number_format": "english",
    })
    if error:
        return SmsResult("unknown" if error == "outcome_unknown" else "failed", error=error)
    if isinstance(data, dict):
        data = next((data[k] for k in ("id", "message_id", "send_request_id", "uid") if k in data), "")
    ref = str(data) if type(data) in (int, str) else ""
    return SmsResult("accepted", provider_id=ref[:128] if re.fullmatch(r"[A-Za-z0-9_-]{1,128}", ref) else "")


def get_balance():
    if settings.SMS_PROVIDER != "faraz":
        return None, "configuration_missing"
    data, error = request("GET", "/ws/v1/account/balance")
    if error or not isinstance(data, dict):
        return None, error or "invalid_balance"
    return {key: data.get(key) for key in ("balanceAmount", "balanceCount") if type(data.get(key)) in (int, float, str)}, ""
