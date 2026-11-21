"""Shared Jalali date conversion and parsing for user-facing dashboard fields."""
from __future__ import annotations

import re
from datetime import date, datetime, time

import jdatetime
from django.utils import timezone

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
_WESTERN_DIGITS = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def to_persian_digits(value) -> str:
    return str(value).translate(_FA_DIGITS)


def to_western_digits(value) -> str:
    return str(value).translate(_WESTERN_DIGITS)


def _local_datetime(value: datetime) -> datetime:
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return timezone.make_aware(value, timezone.get_current_timezone())


def jalali_date_string(value: date | datetime) -> str:
    if isinstance(value, datetime):
        jalali = jdatetime.datetime.fromgregorian(datetime=_local_datetime(value))
    else:
        jalali = jdatetime.date.fromgregorian(date=value)
    return to_persian_digits(jalali.strftime("%Y/%m/%d"))


def jalali_datetime_string(value: date | datetime) -> str:
    if isinstance(value, datetime):
        jalali = jdatetime.datetime.fromgregorian(datetime=_local_datetime(value))
        return to_persian_digits(jalali.strftime("%Y/%m/%d — %H:%M"))
    return jalali_date_string(value)


def jalali_datetime_input(value: date | datetime | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        jalali = jdatetime.datetime.fromgregorian(datetime=_local_datetime(value))
    else:
        jalali = jdatetime.datetime.fromgregorian(datetime=datetime.combine(value, time.min))
    return to_persian_digits(jalali.strftime("%Y/%m/%d %H:%M"))


def parse_local_datetime(value: str | None) -> datetime | None:
    """Parse Persian Jalali input while accepting ISO values from old drafts."""
    if value is None or str(value).strip() == "":
        return None
    raw = to_western_digits(value).strip()
    match = re.fullmatch(
        r"(\d{4})/(\d{1,2})/(\d{1,2})\s+(\d{1,2}):(\d{2})",
        raw,
    )
    if match:
        year, month, day, hour, minute = map(int, match.groups())
        try:
            return jdatetime.datetime(year, month, day, hour, minute).togregorian()
        except ValueError:
            raise ValueError("تاریخ و ساعت شمسی معتبر نیست.") from None
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("تاریخ را به شکل سال/ماه/روز و ساعت وارد کنید.") from None
    if timezone.is_aware(parsed):
        return timezone.localtime(parsed).replace(tzinfo=None)
    return parsed
