"""Single Arvan OpenAI-compatible model. Never log credentials or prompts."""
import json
from urllib.parse import urlsplit
import httpx
from django.conf import settings


class AiError(Exception):
    pass


def endpoint():
    raw = settings.ARVAN_AI_BASE_URL.strip().rstrip("/")
    try:
        p = urlsplit(raw)
        host = p.hostname or ""
        if (p.scheme != "https" or not (host == "arvancloudai.ir" or host.endswith(".arvancloudai.ir"))
                or p.username or p.password or p.query or p.fragment or p.port not in (None, 443)):
            return ""
        return raw if raw.endswith("/chat/completions") else raw + "/chat/completions"
    except ValueError:
        return ""


def available():
    return bool(settings.ARVAN_AI_ENABLED and endpoint() and settings.ARVAN_AI_API_KEY.strip())


def count(value):
    return value if type(value) is int and 0 <= value <= 1000000 else None


def complete(system, context):
    if not available():
        raise AiError("disabled")
    try:
        with httpx.Client(timeout=12.0, follow_redirects=False) as client:
            response = client.post(endpoint(), headers={"Authorization": "apikey " + settings.ARVAN_AI_API_KEY.strip()},
                json={"model": settings.ARVAN_AI_MODEL,
                    "messages": [{"role": "system", "content": system},
                                 {"role": "user", "content": json.dumps(context, ensure_ascii=False)}],
                    "max_tokens": 650, "temperature": .3, "response_format": {"type": "json_object"}})
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or len(content) > 12000:
            raise AiError("invalid_output")
        value = json.loads(content)
        if not isinstance(value, dict):
            raise AiError("invalid_output")
        usage = data.get("usage") or {}
        return value, count(usage.get("prompt_tokens")), count(usage.get("completion_tokens"))
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        raise AiError("provider_unavailable") from None
