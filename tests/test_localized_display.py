from datetime import date, datetime, timezone as utc_timezone

import pytest
from django.utils import timezone

from apps.core.dates import (
    jalali_date_string,
    jalali_datetime_input,
    jalali_datetime_string,
    parse_local_datetime,
)
from apps.core.templatetags.core_filters import (
    currency_label_fa,
    telegram_remote_status_fa,
    user_message_fa,
)
from apps.operations.account_reports import _report_period_label, _rows


def test_jalali_datetime_input_round_trips_persian_digits():
    with timezone.override("Asia/Tehran"):
        parsed = parse_local_datetime("۱۴۰۵/۰۸/۳۰ ۱۲:۱۵")
        assert parsed == datetime(2026, 11, 21, 12, 15)
        assert jalali_datetime_input(parsed) == "۱۴۰۵/۰۸/۳۰ ۱۲:۱۵"


def test_old_iso_schedule_drafts_remain_accepted():
    assert parse_local_datetime("2026-11-21T12:15") == datetime(2026, 11, 21, 12, 15)


def test_invalid_jalali_schedule_is_rejected_with_persian_message():
    with pytest.raises(ValueError, match="تاریخ و ساعت شمسی معتبر نیست"):
        parse_local_datetime("۱۴۰۵/۱۳/۴۰ ۲۵:۹۹")


def test_dashboard_date_format_is_jalali_and_localized():
    with timezone.override("Asia/Tehran"):
        stamp = datetime(2026, 11, 21, 8, 45, tzinfo=utc_timezone.utc)
        assert jalali_date_string(date(2026, 11, 21)) == "۱۴۰۵/۰۸/۳۰"
        assert jalali_datetime_string(stamp) == "۱۴۰۵/۰۸/۳۰ — ۱۲:۱۵"


def test_telegram_account_report_period_is_explained_in_jalali():
    assert _report_period_label(2026, 11) == "از ۱۰ آبان تا ۹ آذر ۱۴۰۵"


def test_account_report_rows_translate_currency_and_dates():
    with timezone.override("Asia/Tehran"):
        stamp = datetime(2026, 11, 21, 8, 45, tzinfo=utc_timezone.utc).timestamp()
        rows = _rows(
            [{"date": stamp, "peer": {"type": "channel"}, "amount": 2, "currency": "XTR"}],
            "transactions",
        )
    assert rows[0][0] == "۱۴۰۵/۰۸/۳۰ — ۱۲:۱۵"
    assert rows[0][1] == "کانال"
    assert rows[0][3] == "استار تلگرام"


def test_provider_codes_are_not_exposed_as_user_facing_labels():
    assert currency_label_fa("XTR") == "استار تلگرام"
    assert telegram_remote_status_fa("on_hold") == "در انتظار"
    assert telegram_remote_status_fa("unmapped_remote_code") == "وضعیت نامشخص"
    assert "Connection" not in user_message_fa("ConnectionError: timeout")
