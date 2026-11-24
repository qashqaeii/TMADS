from __future__ import annotations

import hashlib
import secrets
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone


def constant_time_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a.encode(), b.encode(), strict=False):
        result |= x ^ y
    return result == 0


def verify_webhook_secret(header_value: str | None) -> bool:
    expected = (getattr(settings, "GRAMADS_BOT_WEBHOOK_SECRET", "") or "").strip()
    if not expected:
        return settings.APP_ENV != "PRODUCTION"
    if not header_value:
        return False
    return constant_time_compare(header_value.strip(), expected)


def digest_token(raw: str) -> str:
    pepper = (settings.SECRET_KEY or "")[:32]
    return hashlib.sha256(f"{pepper}:{raw}".encode()).hexdigest()


def generate_link_token() -> str:
    return secrets.token_urlsafe(24)


def rate_limit_allow(telegram_user_id: int, *, limit: int | None = None) -> bool:
    from .config import get_bot_config

    cfg = get_bot_config()
    max_per_min = limit or cfg.max_updates_per_minute or 40
    key = f"tg:rate:{telegram_user_id}:{timezone.now().strftime('%Y%m%d%H%M')}"
    try:
        added = cache.add(key, 1, timeout=70)
        if added:
            return True
        count = cache.incr(key)
        return int(count) <= max_per_min
    except Exception:
        return True


def callback_already_processed(callback_query_id: str) -> bool:
    from .models import TelegramCallbackReceipt

    if not callback_query_id:
        return False
    _, created = TelegramCallbackReceipt.objects.get_or_create(callback_query_id=callback_query_id)
    return not created