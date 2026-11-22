"""ArvanCloud AIaaS OpenAI-compatible provider.

Credentials and endpoint are server-side settings only. Prompts and API keys are
never logged; redirects are disabled so Authorization cannot be forwarded.
"""
import ipaddress
import json
import logging
import time
from urllib.parse import urlsplit, urlunsplit

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)


class AiError(Exception):
    """Safe, user-facing AI error code. Never contains upstream response bodies."""


_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def endpoint():
    """Normalize an Arvan panel URL or a complete chat/completions URL."""
    raw = str(getattr(settings, "ARVAN_AI_BASE_URL", "") or "").strip().rstrip("/")
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").lower()
        if (
            parsed.scheme.lower() != "https"
            or not host
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.port not in (None, 443)
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal"))
        ):
            return ""
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            return ""
        path = parsed.path.rstrip("/")
        if not path:
            return ""
        if not path.lower().endswith("/chat/completions"):
            path += "/chat/completions"
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    except ValueError:
        return ""


def authorization_header():
    """Arvan uses Authorization: apikey <key>; accept a panel-copied prefix."""
    key = str(getattr(settings, "ARVAN_AI_API_KEY", "") or "").strip()
    if not key:
        return ""
    if key.lower().startswith("apikey "):
        key = key.split(None, 1)[1].strip()
    if not key:
        return ""
    return "apikey " + key


def available():
    return bool(
        getattr(settings, "ARVAN_AI_ENABLED", False)
        and endpoint()
        and authorization_header()
        and str(getattr(settings, "ARVAN_AI_MODEL", "") or "").strip()
    )


def ui_visible():
    """Show AI surfaces in the product UI.

    In LOCAL+DEBUG, panels stay visible even without provider credentials so
    placements can be reviewed. Actual API calls still require available().
    """
    if available():
        return True
    return bool(getattr(settings, "DEBUG", False)) and str(
        getattr(settings, "APP_ENV", "") or ""
    ).upper() == "LOCAL"


def count(value):
    return value if type(value) is int and 0 <= value <= 1_000_000 else None


def _message_content(data):
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        return "\n".join(part for part in parts if part).strip()
    return ""


def _retry_after(response):
    try:
        seconds = int(response.headers.get("Retry-After", "0"))
    except (TypeError, ValueError):
        return
    if seconds > 0:
        time.sleep(min(seconds, 2))


def complete(system, context, *, max_tokens=None, temperature=None):
    """Send one bounded JSON-mode request and return parsed data plus token usage."""
    if not available():
        raise AiError("disabled")

    url = endpoint()
    auth = authorization_header()
    timeout = max(3.0, min(float(getattr(settings, "ARVAN_AI_TIMEOUT_SECONDS", 10)), 30.0))
    retries = max(0, min(int(getattr(settings, "ARVAN_AI_MAX_RETRIES", 1)), 2))
    output_tokens = max_tokens if max_tokens is not None else getattr(settings, "ARVAN_AI_MAX_TOKENS", 900)
    output_tokens = max(128, min(int(output_tokens), 2000))
    temp = temperature if temperature is not None else getattr(settings, "ARVAN_AI_TEMPERATURE", 0.2)
    temp = max(0.0, min(float(temp), 1.0))
    user_content = json.dumps(context, ensure_ascii=False, separators=(",", ":"))
    if len(user_content) > 16_000:
        raise AiError("invalid_input")

    payload = {
        "model": settings.ARVAN_AI_MODEL,
        "messages": [
            {"role": "system", "content": str(system or "")},
            {"role": "user", "content": user_content},
        ],
        "temperature": temp,
        "max_tokens": output_tokens,
        "response_format": {"type": "json_object"},
    }

    last_error = "provider_unavailable"
    for attempt in range(retries + 1):
        started = time.perf_counter()
        try:
            with httpx.Client(timeout=timeout, follow_redirects=False) as client:
                response = client.post(
                    url,
                    headers={"Authorization": auth, "Content-Type": "application/json"},
                    json=payload,
                )
        except httpx.TimeoutException:
            last_error = "provider_unavailable"
            if attempt < retries:
                time.sleep(0.2 * (2 ** attempt))
                continue
            raise AiError(last_error) from None
        except httpx.RequestError:
            last_error = "provider_unavailable"
            if attempt < retries:
                time.sleep(0.2 * (2 ** attempt))
                continue
            raise AiError(last_error) from None

        status = response.status_code
        if status in (401, 403):
            raise AiError("provider_auth")
        if status in _RETRYABLE_STATUS:
            last_error = "rate_limited" if status == 429 else "provider_unavailable"
            if attempt < retries:
                _retry_after(response)
                time.sleep(0.2 * (2 ** attempt))
                continue
            raise AiError(last_error)
        if status >= 400:
            raise AiError("provider_unavailable")

        try:
            data = response.json()
        except (ValueError, TypeError):
            raise AiError("invalid_output") from None
        content = _message_content(data)
        if not content or len(content) > 12_000:
            raise AiError("invalid_output")
        try:
            parsed = json.loads(content)
        except (ValueError, TypeError):
            raise AiError("invalid_output") from None
        if not isinstance(parsed, dict):
            raise AiError("invalid_output")

        usage = data.get("usage") if isinstance(data, dict) else {}
        usage = usage if isinstance(usage, dict) else {}
        input_tokens = count(usage.get("prompt_tokens"))
        output_tokens_used = count(usage.get("completion_tokens"))
        logger.info(
            "arvan_ai_complete model=%s latency_ms=%s input_tokens=%s output_tokens=%s",
            str(data.get("model") or settings.ARVAN_AI_MODEL)[:80],
            int((time.perf_counter() - started) * 1000),
            input_tokens,
            output_tokens_used,
        )
        return parsed, input_tokens, output_tokens_used

    raise AiError(last_error)
