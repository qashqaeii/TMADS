"""Explainable, conservative performance advice from official lifetime stats.

No model promises, fake estimates, automatic CPM changes, or customer writes.
"""
from decimal import Decimal, InvalidOperation

from apps.campaigns.models import Campaign


def campaign_advice(campaign, metrics):
    if not campaign.remote_ads.exclude(remote_ad_id="").exists():
        return []
    if metrics.get("stats_stale"):
        return [{
            "tone": "muted", "title": "داده به‌روز نیست",
            "body": "ابتدا آمار تبلیغ را از تلگرام همگام کنید. پیشنهاد عملکردی با داده قدیمی داده نمی‌شود.",
        }]
    if not metrics.get("has_stats"):
        return []
    suggestions = []
    if campaign.status == Campaign.Status.REJECTED:
        suggestions.append({
            "tone": "warning", "title": "بررسی علت رد تبلیغ",
            "body": "وضعیت ردشدن را در تلگرام بررسی کنید و پیش از ساخت نسخه جدید، قوانین محتوا و مقصد را مرور کنید.",
        })
    if (metrics.get("has_ctr") and metrics.get("impressions", 0) >= 2000
            and metrics.get("ctr", 0) < 0.5):
        suggestions.append({
            "tone": "info", "title": "بازبینی متن و پیشنهاد تبلیغ",
            "body": "تبلیغ حداقل ۲۰۰۰ نمایش دارد اما نرخ کلیک زیر نیم درصد است. متن، مقصد و تناسب مخاطبان را بررسی کنید. این یک پیشنهاد مبتنی بر آستانه است.",
        })
    if (metrics.get("has_actions") and metrics.get("has_clicks")
            and metrics.get("action_type") and metrics.get("clicks", 0) >= 30
            and metrics.get("actions", 0) == 0):
        suggestions.append({
            "tone": "warning", "title": "کنترل مسیر تبدیل",
            "body": "حداقل ۳۰ کلیک ثبت شده اما برای نوع اقدام انتخابی نتیجه‌ای گزارش نشده است. عملکرد لینک، مقصد یا پیکسل را بررسی کنید.",
        })
    if metrics.get("currency") == "TON":
        spent = metrics.get("spent_ton")
        remaining = metrics.get("remaining_ton")
        if (isinstance(spent, Decimal) and isinstance(remaining, Decimal)
                and spent.is_finite() and remaining.is_finite()
                and spent >= 0 and remaining >= 0 and spent + remaining > 0
                and remaining / (spent + remaining) <= Decimal(".10")):
            suggestions.append({
                "tone": "info", "title": "مانده بودجه کم است",
                "body": "مانده اعتبار تلگرام کمتر از ۱۰ درصد مجموع مصرف و مانده است. در صورت نیاز درخواست افزایش بودجه را بررسی کنید.",
            })
    return suggestions[:3]
