"""Staff-only, on-demand read surface. Never exposes shared account data to customers."""
import calendar
import re
from datetime import date, datetime, timezone as utc_timezone
from urllib.parse import quote

import jdatetime
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.utils import timezone

from apps.accounts.permissions import staff_ops_required
from apps.core.dates import jalali_datetime_string, to_persian_digits, to_western_digits
from apps.core.templatetags.core_filters import (
    currency_label_fa,
    telegram_event_type_fa,
    telegram_peer_type_fa,
    telegram_transfer_status_fa,
)
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError


SECTIONS = [
    ("report", "گزارش ماهانه"), ("stats", "آمار دوره‌ای"), ("transactions", "تراکنش حساب"),
    ("transfer", "وضعیت انتقال"), ("accounts", "حساب‌های مرتبط"), ("audiences", "مخاطبان"),
    ("pixels", "پیکسل و رویدادها"),
]
COLS = {
    "report": [("ad_id", "شناسه"), ("ad_title", "عنوان تبلیغ"), ("views", "نمایش"),
               ("opens", "بازشدن ویدیو"), ("clicks", "کلیک"), ("actions", "اقدام"),
               ("spent_budget", "هزینه"), ("currency", "ارز")],
    "stats": [("from_time", "شروع بازه (شمسی)"), ("views", "نمایش"),
              ("opens", "بازشدن ویدیو"), ("clicks", "کلیک"), ("actions", "اقدام"),
              ("spent_budget", "هزینه"), ("currency", "ارز")],
    "transactions": [("date", "زمان ثبت (شمسی)"), ("peer_type", "نوع تراکنش"),
                     ("amount", "مبلغ"), ("currency", "ارز")],
    "transfer": [("transaction_id", "شناسه"), ("status", "وضعیت"),
                 ("amount", "مبلغ"), ("currency", "ارز")],
    "accounts": [("account_id", "شناسه حساب"), ("title", "عنوان"),
                 ("remaining_budget", "اعتبار آزاد"), ("ads_budget", "اعتبار تبلیغات"),
                 ("spent_budget", "مصرف"), ("currency", "ارز")],
    "audiences": [("audience_id", "شناسه"), ("title", "عنوان"),
                  ("size", "اندازه تقریبی"), ("ads_count", "تعداد تبلیغات")],
    "pixels": [("event_id", "شناسه رویداد"), ("title", "عنوان"), ("type", "نوع"),
               ("status", "وضعیت"), ("ads_count", "تعداد تبلیغات")],
}
_JALALI_MONTHS = (
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
)


def _integer(raw, low, high, label):
    try:
        value = int(to_western_digits(raw))
        if not low <= value <= high:
            raise ValueError
        return value
    except (TypeError, ValueError):
        raise ValueError(label + " معتبر نیست.") from None


def _report_period_label(year: int, month: int) -> str:
    start = date(year, month, 1)
    end = date(year, month, calendar.monthrange(year, month)[1])
    jalali_start = jdatetime.date.fromgregorian(date=start)
    jalali_end = jdatetime.date.fromgregorian(date=end)
    start_day = to_persian_digits(jalali_start.day)
    end_day = to_persian_digits(jalali_end.day)
    end_year = to_persian_digits(jalali_end.year)
    if jalali_start.year == jalali_end.year and jalali_start.month == jalali_end.month:
        return f"از {start_day} تا {end_day} {_JALALI_MONTHS[jalali_end.month - 1]} {end_year}"
    start_label = f"{start_day} {_JALALI_MONTHS[jalali_start.month - 1]}"
    if jalali_start.year != jalali_end.year:
        start_label += f" {to_persian_digits(jalali_start.year)}"
    return f"از {start_label} تا {end_day} {_JALALI_MONTHS[jalali_end.month - 1]} {end_year}"


def _report_month_choices(current: date):
    year, month = current.year, current.month
    choices = []
    while year > 2021 or (year == 2021 and month >= 1):
        choices.append((f"{year:04d}-{month:02d}", _report_period_label(year, month)))
        month -= 1
        if month == 0:
            year -= 1
            month = 12
    return choices


def _parse_report_period(raw, fallback_year: int, fallback_month: int):
    if not raw:
        return fallback_year, fallback_month
    match = re.fullmatch(r"(\d{4})-(\d{1,2})", to_western_digits(raw).strip())
    if not match:
        raise ValueError("بازه گزارش معتبر نیست.")
    year, month = int(match.group(1)), int(match.group(2))
    if not 2021 <= year <= fallback_year or not 1 <= month <= 12:
        raise ValueError("بازه گزارش معتبر نیست.")
    if year == fallback_year and month > fallback_month:
        raise ValueError("بازه گزارش هنوز در دسترس نیست.")
    return year, month


def _display_timestamp(raw):
    try:
        if isinstance(raw, (int, float)) or str(raw).strip().isdigit():
            # Telegram data may use Unix seconds or milliseconds.
            timestamp = float(raw)
            if abs(timestamp) >= 100_000_000_000:
                timestamp /= 1000
            value = datetime.fromtimestamp(timestamp, tz=utc_timezone.utc)
        else:
            value = datetime.fromisoformat(str(raw).strip().replace("Z", "+00:00"))
            if timezone.is_naive(value):
                value = timezone.make_aware(value, utc_timezone.utc)
        return jalali_datetime_string(value)
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def _rows(items, section):
    if not isinstance(items, list) or any(not isinstance(item, dict) for item in items):
        raise ValueError("ساختار پاسخ گزارش معتبر نیست.")
    output = []
    for item in items:
        row = dict(item)
        if section == "transactions":
            peer = row.get("peer")
            peer_type = peer.get("type") if isinstance(peer, dict) else None
            row["peer_type"] = telegram_peer_type_fa(peer_type)
        for key in ("date", "from_time"):
            if key in row:
                row[key] = _display_timestamp(row[key])
        if "currency" in row:
            row["currency"] = currency_label_fa(row["currency"])
        if "status" in row:
            row["status"] = telegram_transfer_status_fa(row["status"])
        if section == "pixels" and "type" in row:
            row["type"] = telegram_event_type_fa(row["type"])
        output.append([
            row.get(key) if isinstance(row.get(key), (str, int, float)) else "—"
            for key, _ in COLS[section]
        ])
    return [[value if value is not None and value != "" else "—" for value in row] for row in output]


@login_required
@staff_ops_required
@require_GET
def account_workspace(request):
    now = timezone.now()
    local_now = timezone.localtime(now)
    current_year, current_month = local_now.year, local_now.month
    section = request.GET.get("section", "report")
    if section not in COLS:
        section = "report"

    legacy_period = ""
    if request.GET.get("year") or request.GET.get("month"):
        try:
            legacy_year = _integer(request.GET.get("year", current_year), 2021, current_year, "سال")
            legacy_month = _integer(request.GET.get("month", current_month), 1, 12, "ماه")
            legacy_period = f"{legacy_year:04d}-{legacy_month:02d}"
        except ValueError:
            legacy_period = ""
    selected_period = request.GET.get("period") or legacy_period or f"{current_year:04d}-{current_month:02d}"
    month_choices = _report_month_choices(date(current_year, current_month, 1))
    choice_labels = dict(month_choices)
    ctx = {
        "sections": SECTIONS,
        "section": section,
        "columns": [label for _, label in COLS[section]],
        "report_period": selected_period,
        "report_month_choices": month_choices,
        "report_period_label": choice_labels.get(selected_period, ""),
        "interval": request.GET.get("interval", "86400"),
        "transaction_id": request.GET.get("transaction_id", "")[:128],
        "offset": request.GET.get("offset", ""),
        "loaded": False,
    }
    if request.GET.get("load") != "1":
        return render(request, "operations/telegram_account.html", ctx)

    try:
        key = f"tmads:ops:account_report:{request.user.pk}"
        if not cache.add(key, True, 2):
            raise ValueError("لطفاً چند لحظه صبر کنید و دوباره تلاش کنید.")
        client = TelegramAdsClient()
        next_offset = None
        if section == "report":
            year, month = _parse_report_period(selected_period, current_year, current_month)
            ctx["report_period_label"] = _report_period_label(year, month)
            items = client.get_account_report(year, month)
        elif section == "stats":
            interval = _integer(ctx["interval"], 300, 86400, "بازه")
            if interval not in {300, 86400}:
                raise ValueError("بازه باید روزانه یا پنج دقیقه‌ای باشد.")
            end = int(now.timestamp()) // interval * interval
            start = end - (288 if interval == 300 else 30) * interval
            items = client.get_account_statistics(from_time=start, to_time=end, interval=interval)
        elif section == "transfer":
            tx = ctx["transaction_id"].strip()
            if not tx or len(request.GET.get("transaction_id", "")) > 128:
                raise ValueError("شناسه انتقال معتبر نیست.")
            item = client.get_transaction_status(tx)
            if item.get("transaction_id") != tx:
                raise ValueError("شناسه پاسخ با درخواست مطابقت ندارد.")
            items = [item]
        elif section == "transactions":
            cursor = ctx["offset"][:512] or None
            data = client.get_account_transactions(offset=cursor, limit=50)
            items = data.get("transactions")
            next_offset = data.get("next_offset")
        else:
            offset = _integer(ctx["offset"] or "0", 0, 1000000, "صفحه")
            if section == "accounts":
                data = client.get_related_accounts(offset=offset, limit=50)
                items = data.get("accounts")
            elif section == "audiences":
                data = client.get_audiences(offset=offset, limit=50)
                items = data.get("audiences")
            else:
                data = client.get_pixel_events(offset=offset, limit=50)
                items = data.get("events")
            total = data.get("total_count")
            if isinstance(items, list) and type(total) is int and items and offset + len(items) < total:
                next_offset = offset + len(items)

        rows = _rows(items, section)
        ctx.update({
            "loaded": True,
            "rows": rows,
            "next_offset": next_offset,
            "row_count": len(rows),
            "fetched_at": timezone.now(),
        })
        if request.GET.get("export") == "csv":
            import csv
            response = HttpResponse(content_type="text/csv; charset=utf-8")
            filename = quote("گزارش-حساب-تلگرام.csv")
            response["Content-Disposition"] = f"attachment; filename*=UTF-8''{filename}"
            response.write("\ufeff")
            writer = csv.writer(response)
            writer.writerow(ctx["columns"])
            for row in rows:
                writer.writerow([
                    "'" + str(value) if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value
                    for value in row
                ])
            response["Cache-Control"] = "private, no-store"
            return response
    except ValueError as exc:
        ctx["error"] = str(exc)
    except TelegramAdsError:
        ctx["error"] = "اطلاعات از تلگرام دریافت نشد؛ وضعیت مجوز یا اتصال را بررسی کنید."
    response = render(request, "operations/telegram_account.html", ctx)
    response["Cache-Control"] = "private, no-store"
    return response
