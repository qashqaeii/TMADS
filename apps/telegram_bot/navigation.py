from __future__ import annotations

from .models import TelegramMenuSession


HOME = "home"
GUEST_HOME = "guest_home"
ADMIN_HOME = "admin_home"


def get_session(telegram_user_id: int, chat_id: int) -> TelegramMenuSession:
    session, created = TelegramMenuSession.objects.get_or_create(
        telegram_user_id=telegram_user_id,
        defaults={"chat_id": chat_id},
    )
    if session.chat_id != chat_id:
        session.chat_id = chat_id
        session.save(update_fields=["chat_id", "updated_at"])
    return session


def reset_to(session: TelegramMenuSession, screen: str, *, panel: str | None = None, clear_context: bool = False):
    session.nav_stack = [screen]
    if clear_context:
        session.context = {}
    if panel:
        session.panel = panel
    session.save(update_fields=["nav_stack", "context", "panel", "updated_at"])


def push_screen(session: TelegramMenuSession, screen: str):
    stack = list(session.nav_stack or [])
    if not stack or stack[-1] != screen:
        stack.append(screen)
    session.nav_stack = stack[-12:]
    session.save(update_fields=["nav_stack", "updated_at"])


def pop_screen(session: TelegramMenuSession) -> str:
    stack = list(session.nav_stack or [HOME])
    if len(stack) > 1:
        stack.pop()
    session.nav_stack = stack
    session.save(update_fields=["nav_stack", "updated_at"])
    return stack[-1]


def current_screen(session: TelegramMenuSession) -> str:
    stack = session.nav_stack or [HOME]
    return stack[-1] if stack else HOME


def set_context_value(session: TelegramMenuSession, key: str, value):
    ctx = dict(session.context or {})
    ctx[key] = value
    session.context = ctx
    session.save(update_fields=["context", "updated_at"])


def get_context_value(session: TelegramMenuSession, key: str, default=None):
    return (session.context or {}).get(key, default)