from __future__ import annotations

from .bot import get_bot

_GROUP_REPLY = (
    "این ربات فقط در چت خصوصی (Private) با شما کار می‌کند.\n"
    "برای امنیت، اطلاعات حساب در گروه نمایش داده نمی‌شود."
)


def is_private_chat(chat: dict | None) -> bool:
    return (chat or {}).get("type") == "private"


def refuse_non_private(chat_id: int | None) -> bool:
    """Return True if update was refused (non-private chat)."""
    if chat_id is None:
        return True
    bot = get_bot()
    if bot:
        try:
            bot.send_message(chat_id, _GROUP_REPLY, disable_web_page_preview=True)
        except Exception:
            pass
    return True