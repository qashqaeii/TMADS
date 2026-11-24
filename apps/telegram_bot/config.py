from __future__ import annotations

from django.conf import settings

from .models import TelegramBotConfig


def bot_token_configured() -> bool:
    return bool((getattr(settings, "GRAMADS_BOT_TOKEN", "") or "").strip())


def bot_runtime_enabled() -> bool:
    if not bot_token_configured():
        return False
    cfg = get_bot_config()
    return bool(cfg.enabled)


def get_bot_config() -> TelegramBotConfig:
    row, _ = TelegramBotConfig.objects.get_or_create(singleton_key="default")
    return row