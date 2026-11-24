from __future__ import annotations

from telebot import types


def inline_grid(pairs: list[tuple[str, str]], *, columns: int = 2) -> types.InlineKeyboardMarkup:
  """pairs: list of (text, callback_data)"""
  kb = types.InlineKeyboardMarkup()
  row: list[types.InlineKeyboardButton] = []
  for text, data in pairs:
      if len(data.encode("utf-8")) > 64:
          raise ValueError(f"callback_data too long: {data}")
      row.append(types.InlineKeyboardButton(text=text, callback_data=data))
      if len(row) >= columns:
          kb.row(*row)
          row = []
  if row:
      kb.row(*row)
  return kb


def nav_row(*, back: bool = True, home: bool = True, close: bool = False) -> list[types.InlineKeyboardButton]:
    buttons = []
    if back:
        buttons.append(types.InlineKeyboardButton("◀️ بازگشت", callback_data="nav:back"))
    if home:
        buttons.append(types.InlineKeyboardButton("🏠 خانه", callback_data="nav:home"))
    if close:
        buttons.append(types.InlineKeyboardButton("✖️ بستن", callback_data="nav:close"))
    return buttons


def attach_nav(kb: types.InlineKeyboardMarkup, *, back: bool = True, home: bool = True, close: bool = False):
    kb.row(*nav_row(back=back, home=home, close=close))
    return kb