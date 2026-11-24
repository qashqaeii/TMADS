from __future__ import annotations

from django.conf import settings

_bot = None


def get_bot():
    global _bot
    if _bot is not None:
        return _bot
    token = (getattr(settings, "GRAMADS_BOT_TOKEN", "") or "").strip()
    if not token:
        return None
    from telebot import TeleBot

    _bot = TeleBot(token, threaded=False, parse_mode="HTML")
    return _bot


def reset_bot_for_tests():
    global _bot
    _bot = None