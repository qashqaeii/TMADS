from __future__ import annotations

import html

from django.urls import reverse

from apps.core.dates import jalali_datetime_string, to_persian_digits
from apps.finance.services.money import irr_to_toman_int


def escape_html(value) -> str:
    """Escape user/database text for Telegram HTML parse mode."""
    return html.escape(str(value or ""), quote=False)


def format_toman(irr: int) -> str:
    toman = irr_to_toman_int(int(irr or 0))
    return to_persian_digits(f"{toman:,}".replace(",", "٬"))


def format_int(value: int) -> str:
    return to_persian_digits(f"{int(value):,}".replace(",", "٬"))


def format_pct(value: float) -> str:
    return to_persian_digits(f"{value:.1f}٪")


def site_url(path: str) -> str:
    from django.conf import settings

    base = (settings.PUBLIC_SITE_URL or "").rstrip("/")
    if not base:
        return path
    if not path.startswith("/"):
        path = "/" + path
    return f"{base}{path}"


def named_site_url(route_name: str, *args, **kwargs) -> str:
    return site_url(reverse(route_name, args=args, kwargs=kwargs))