import json

import pytest
from telead.inputs import InputAdSchedule

from apps.campaigns.schedule_utils import (
    IRAN_SCHEDULE_TIMEZONE_SEC,
    parse_schedule_payload,
    preset_business_hours,
    schedule_summary_rows,
    weekdays_for_ui,
)
from apps.telegram_ads.services.ad_payload import build_schedule


def test_iran_timezone_in_api_allowed_offsets():
    sched = InputAdSchedule([0, 0, 0, 0, 0, 0, 0], timezone=IRAN_SCHEDULE_TIMEZONE_SEC)
    sched.validate()


def test_parse_schedule_payload_requires_enabled():
    masks = preset_business_hours()
    data = {
        "schedule_enabled": "1",
        "schedule_json": json.dumps({"week_hours_mask": masks}),
        "schedule_timezone": str(IRAN_SCHEDULE_TIMEZONE_SEC),
    }
    out = parse_schedule_payload(data)
    assert out is not None
    assert len(out["week_hours_mask"]) == 7
    built = build_schedule({"schedule": out})
    assert built is not None
    payload = built.to_dict()
    assert payload["timezone"] == IRAN_SCHEDULE_TIMEZONE_SEC


def test_disabled_schedule_returns_none():
    assert parse_schedule_payload({"schedule_enabled": ""}) is None


def test_weekdays_ui_iranian_order_saturday_to_friday():
    days = weekdays_for_ui()
    assert [d["label"] for d in days] == [
        "شنبه",
        "یکشنبه",
        "دوشنبه",
        "سه‌شنبه",
        "چهارشنبه",
        "پنج‌شنبه",
        "جمعه",
    ]
    assert [d["index"] for d in days] == [5, 6, 0, 1, 2, 3, 4]


def test_schedule_summary_rows_compress_hour_ranges():
    masks = preset_business_hours()
    rows = schedule_summary_rows({"week_hours_mask": masks})
    assert rows
    assert rows[0]["day"] == "دوشنبه"
    assert rows[0]["hours"] == "۰۹–۱۷"
    assert all("·" not in row["hours"] for row in rows)
