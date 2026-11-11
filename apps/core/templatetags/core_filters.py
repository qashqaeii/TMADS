import json

import jdatetime
from django import template
from django.utils import timezone

register = template.Library()

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _to_fa_digits(text: str) -> str:
    return text.translate(_FA_DIGITS)


@register.filter
def persian_digits(value):
    if value is None:
        return ""
    return _to_fa_digits(str(value))


@register.filter
def rate_source_fa(value):
    labels = {
        "nobitex": "نوبیتکس",
        "manual": "دستی",
        "fallback": "حالت پشتیبان",
    }
    key = (value or "").lower() if isinstance(value, str) else ""
    return labels.get(key, value or "—")


@register.filter
def rate_type_fa(value):
    labels = {
        "vwap": "میانگین وزنی دفتر سفارش",
        "best_ask": "پیشنهاد فروش",
        "legacy": "محاسبه ساده",
    }
    key = (value or "").lower() if isinstance(value, str) else ""
    return labels.get(key, value or "—")


@register.filter
def irr_to_toman(value):
    """Display helper: 1 Toman = 10 Rial (stored amounts are IRR integers)."""
    try:
        return int(value) // 10
    except (TypeError, ValueError):
        return 0


@register.filter
def format_irr(value):
    try:
        n = int(value)
        text = f"{n:,}".replace(",", "٬")
        return _to_fa_digits(text)
    except (TypeError, ValueError):
        return "۰"


@register.filter
def jalali_datetime(value):
    if not value:
        return "—"
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone.get_current_timezone())
    local = timezone.localtime(value)
    j = jdatetime.datetime.fromgregorian(datetime=local)
    text = j.strftime("%Y/%m/%d — %H:%M")
    return _to_fa_digits(text)


@register.filter
def jalali_date(value):
    if not value:
        return "—"
    if hasattr(value, "year") and not hasattr(value, "hour"):
        j = jdatetime.date.fromgregorian(date=value)
        return _to_fa_digits(j.strftime("%Y/%m/%d"))
    return jalali_datetime(value)


@register.filter
def campaign_status_label(code: str) -> str:
    from apps.campaigns.models import Campaign

    try:
        return Campaign.Status(code).label
    except ValueError:
        return code or "—"


@register.filter
def campaign_status_class(status: str) -> str:
    mapping = {
        "active": "status-active",
        "paused": "status-warn",
        "draft": "status-draft",
        "paid": "status-info",
        "rejected": "status-danger",
        "failed": "status-danger",
        "awaiting_telegram": "status-warn",
        "pending_review": "status-warn",
    }
    return mapping.get(status, "status-draft")


@register.filter
def to_json(value):
    return json.dumps(value, ensure_ascii=False)


@register.filter
def format_ton(value):
    if value is None or value == "":
        return "—"
    try:
        d = float(value)
        text = f"{d:,.4f}".rstrip("0").rstrip(".")
        text = text.replace(",", "٬")
        return _to_fa_digits(text)
    except (TypeError, ValueError):
        return "—"


@register.filter
def format_count(value):
    try:
        from decimal import Decimal

        if isinstance(value, Decimal):
            n = int(value)
        else:
            n = int(value)
        text = f"{n:,}".replace(",", "٬")
        return _to_fa_digits(text)
    except (TypeError, ValueError):
        return "—"


@register.filter
def shorten_url(value, max_len=28):
    if not value:
        return "—"
    s = str(value).replace("https://", "").replace("http://", "")
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


@register.filter
def tabular(value):
    return value
