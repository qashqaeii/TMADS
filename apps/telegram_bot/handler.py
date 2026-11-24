from __future__ import annotations

import logging

from django.utils import timezone

from .bot import get_bot
from .chat_guard import is_private_chat, refuse_non_private
from .config import bot_runtime_enabled
from .formatters import escape_html
from .navigation import (
    ADMIN_HOME,
    GUEST_HOME,
    HOME,
    current_screen,
    get_session,
    pop_screen,
    push_screen,
    reset_to,
)
from .permissions import active_customer_link, active_staff_link
from .screens import build_screen
from .security import callback_is_processed, rate_limit_allow, record_callback_processed
from .services.link import consume_link_token, revoke_link

logger = logging.getLogger(__name__)


def _answer_callback(call: dict, text: str = ""):
    bot = get_bot()
    if not bot:
        return
    try:
        bot.answer_callback_query(call["id"], text=text[:180] if text else None)
    except Exception:
        pass


def _render(chat_id: int, telegram_user_id: int, screen_id: str, session, *, edit_message_id: int | None):
    screen = build_screen(screen_id, telegram_user_id=telegram_user_id, session=session)
    bot = get_bot()
    if not bot:
        return
    try:
        if edit_message_id:
            bot.edit_message_text(
                screen.text,
                chat_id,
                edit_message_id,
                reply_markup=screen.keyboard,
                disable_web_page_preview=True,
                parse_mode="HTML",
            )
            session.menu_message_id = edit_message_id
        else:
            msg = bot.send_message(
                chat_id,
                screen.text,
                reply_markup=screen.keyboard,
                disable_web_page_preview=True,
                parse_mode="HTML",
            )
            session.menu_message_id = msg.message_id
        session.save(update_fields=["menu_message_id", "updated_at"])
    except Exception as exc:
        if "message is not modified" not in str(exc).lower():
            logger.warning("telegram render failed: %s", exc)


def _touch_link(telegram_user_id: int):
    link = active_customer_link(telegram_user_id)
    if link:
        TelegramUserLink = link.__class__
        TelegramUserLink.objects.filter(pk=link.pk).update(last_seen_at=timezone.now())


def _commit_callback(call: dict) -> None:
    cb_id = call.get("id")
    if cb_id:
        record_callback_processed(str(cb_id))


def process_update_payload(payload: dict) -> None:
    if not bot_runtime_enabled():
        return
    if "callback_query" in payload:
        _process_callback(payload["callback_query"], payload.get("update_id"))
        return
    if "message" in payload:
        _process_message(payload["message"])
        return


def _process_message(message: dict) -> None:
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    user = message.get("from") or {}
    telegram_user_id = user.get("id")
    if not chat_id or not telegram_user_id:
        return
    if not is_private_chat(chat):
        refuse_non_private(int(chat_id))
        return
    if not rate_limit_allow(int(telegram_user_id)):
        return
    text = (message.get("text") or "").strip()
    session = get_session(int(telegram_user_id), int(chat_id))
    _touch_link(int(telegram_user_id))

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) > 1 and parts[1].startswith("link_"):
            raw = parts[1][5:]
            try:
                consume_link_token(
                    raw,
                    telegram_user_id=int(telegram_user_id),
                    chat_id=int(chat_id),
                    telegram_username=user.get("username") or "",
                )
                reset_to(session, HOME, panel="customer", clear_context=True)
                _render(int(chat_id), int(telegram_user_id), HOME, session, edit_message_id=None)
            except ValueError as exc:
                bot = get_bot()
                if bot:
                    bot.send_message(
                        chat_id,
                        f"❌ {escape_html(str(exc))}",
                        parse_mode="HTML",
                    )
            return
        reset_to(session, HOME if active_customer_link(int(telegram_user_id)) else GUEST_HOME, clear_context=True)
        screen = HOME if active_customer_link(int(telegram_user_id)) else GUEST_HOME
        _render(int(chat_id), int(telegram_user_id), screen, session, edit_message_id=None)
        return

    if text in ("/help", "help", "راهنما"):
        reset_to(session, "c:guest:link", clear_context=False)
        _render(int(chat_id), int(telegram_user_id), "c:guest:link", session, edit_message_id=session.menu_message_id)
        return

    screen = HOME if active_customer_link(int(telegram_user_id)) else GUEST_HOME
    reset_to(session, screen)
    _render(int(chat_id), int(telegram_user_id), screen, session, edit_message_id=session.menu_message_id)


def _process_callback(call: dict, update_id: int | None) -> None:
    user = call.get("from") or {}
    message = call.get("message") or {}
    chat = message.get("chat") or {}
    telegram_user_id = user.get("id")
    chat_id = chat.get("id")
    if not telegram_user_id or not chat_id:
        return
    cb_id = str(call.get("id") or "")
    if cb_id and callback_is_processed(cb_id):
        _answer_callback(call)
        return
    if not is_private_chat(chat):
        refuse_non_private(int(chat_id))
        _answer_callback(call)
        return
    if not rate_limit_allow(int(telegram_user_id)):
        _answer_callback(call, "لطفاً چند ثانیه صبر کنید.")
        return
    data = (call.get("data") or "").strip()
    session = get_session(int(telegram_user_id), int(chat_id))
    edit_id = message.get("message_id")
    _touch_link(int(telegram_user_id))

    if data == "nav:back":
        screen = pop_screen(session)
        _answer_callback(call)
        _render(int(chat_id), int(telegram_user_id), screen, session, edit_message_id=edit_id)
        _commit_callback(call)
        return
    if data == "nav:home":
        link = active_customer_link(int(telegram_user_id))
        screen = HOME if link else GUEST_HOME
        reset_to(session, screen, panel="customer" if link else "guest", clear_context=False)
        _answer_callback(call)
        _render(int(chat_id), int(telegram_user_id), screen, session, edit_message_id=edit_id)
        _commit_callback(call)
        return
    if data == "nav:admin":
        staff = active_staff_link(int(telegram_user_id))
        if not staff:
            _answer_callback(call, "دسترسی مدیریتی ندارید.")
            _commit_callback(call)
            return
        reset_to(session, ADMIN_HOME, panel="admin")
        _answer_callback(call)
        _render(int(chat_id), int(telegram_user_id), ADMIN_HOME, session, edit_message_id=edit_id)
        _commit_callback(call)
        return
    if data == "nav:close":
        bot = get_bot()
        if bot and edit_id:
            try:
                bot.delete_message(chat_id, edit_id)
            except Exception:
                pass
        _answer_callback(call)
        _commit_callback(call)
        return
    if data.startswith("go:"):
        screen = data[3:]
        push_screen(session, screen)
        _answer_callback(call)
        _render(int(chat_id), int(telegram_user_id), screen, session, edit_message_id=edit_id)
        _commit_callback(call)
        return
    if data == "act:disc:yes":
        link = active_customer_link(int(telegram_user_id))
        if link:
            revoke_link(link, reason="درخواست کاربر در ربات")
        reset_to(session, GUEST_HOME, panel="guest", clear_context=True)
        _answer_callback(call, "اتصال قطع شد.")
        _render(int(chat_id), int(telegram_user_id), GUEST_HOME, session, edit_message_id=edit_id)
        _commit_callback(call)
        return
    screen = current_screen(session)
    _answer_callback(call)
    _render(int(chat_id), int(telegram_user_id), screen, session, edit_message_id=edit_id)
    _commit_callback(call)