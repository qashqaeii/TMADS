"""Weekly ad schedule parsing for Telegram Ads InputAdSchedule."""

from __future__ import annotations

import json
from typing import Any

from telead.inputs import InputAdSchedule

# Iran (UTC+3:30) — accepted offset per telead.limits.SCHEDULE_TIMEZONES
IRAN_SCHEDULE_TIMEZONE_SEC = 12600

WEEKDAY_LABELS_FA = (
    "دوشنبه",
    "سه‌شنبه",
    "چهارشنبه",
    "پنج‌شنبه",
    "جمعه",
    "شنبه",
    "یکشنبه",
)


def empty_week_mask() -> list[int]:
    return [0] * 7


def toggle_hour(mask: int, hour: int) -> int:
    if not 0 <= hour <= 23:
        raise ValueError("hour out of range")
    return mask ^ (1 << hour)


def hours_from_mask(mask: int) -> list[int]:
    return [h for h in range(24) if (mask >> h) & 1]


def parse_schedule_payload(data) -> dict[str, Any] | None:
    """Build canonical schedule dict from POST or None if disabled/empty."""
    if not data.get("schedule_enabled"):
        return None

    raw = data.get("schedule_json") or ""
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return None
    masks = parsed.get("week_hours_mask") if isinstance(parsed, dict) else None
    if not isinstance(masks, list) or len(masks) != 7:
        return None
    try:
        masks_int = [int(m) for m in masks]
    except (TypeError, ValueError):
        return None
    if not any(masks_int):
        return None
    tz_raw = data.get("schedule_timezone")
    if tz_raw in (None,""):
        tz_raw = parsed.get("timezone",IRAN_SCHEDULE_TIMEZONE_SEC)
    if tz_raw is None:
        tz_raw=IRAN_SCHEDULE_TIMEZONE_SEC
    try:
        tz = int(tz_raw)
    except (TypeError, ValueError):
        return None
    use_viewer = data.get("schedule_viewer_timezone") == "1"
    if use_viewer:
        tz=None
    schedule = InputAdSchedule(
        week_hours_mask=masks_int,
        timezone=tz,
        use_viewer_timezone=use_viewer,
    )
    try:
        schedule.validate()
        return schedule.to_dict()
    except (TypeError, ValueError, OverflowError):
        return None


def schedule_summary_fa(schedule: dict[str, Any] | None) -> str:
    if not schedule or not schedule.get("week_hours_mask"):
        return "بدون محدودیت ساعتی (نمایش در تمام ساعات)"
    masks = schedule["week_hours_mask"]
    parts: list[str] = []
    for idx, mask in enumerate(masks):
        hours = hours_from_mask(int(mask))
        if not hours:
            continue
        hr_txt = "، ".join(f"{h:02d}" for h in hours)
        parts.append(f"{WEEKDAY_LABELS_FA[idx]}: {hr_txt}")
    return " · ".join(parts) if parts else "بدون بازهٔ انتخاب‌شده"


def preset_business_hours() -> list[int]:
    """Mon–Fri 9–17 (exclusive 18)."""
    masks = empty_week_mask()
    work_mask = sum(1 << h for h in range(9, 18))
    for i in range(5):
        masks[i] = work_mask
    return masks


def schedule_timezone_choices():
    from telead.limits import SCHEDULE_TIMEZONES
    from apps.core.dates import to_persian_digits

    choices = []
    for offset in sorted(SCHEDULE_TIMEZONES):
        if offset == 0:
            label = "گرینویچ (بدون اختلاف)"
        elif offset == IRAN_SCHEDULE_TIMEZONE_SEC:
            label = "ایران (۳:۳۰+)"
        else:
            sign = "+" if offset > 0 else "−"
            hours, remainder = divmod(abs(offset), 3600)
            minutes = remainder // 60
            hour_text = to_persian_digits(str(hours).zfill(2))
            minute_text = to_persian_digits(str(minutes).zfill(2))
            label = f"اختلاف با گرینویچ: {sign}{hour_text}:{minute_text}"
        choices.append((offset, label))
    return choices
