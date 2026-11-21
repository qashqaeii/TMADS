import json
import re

from django import template

from apps.core.dates import (
    jalali_date_string,
    jalali_datetime_input,
    jalali_datetime_string,
    to_persian_digits,
)

register = template.Library()


def _to_fa_digits(text: str) -> str:
    return to_persian_digits(text)


@register.filter
def persian_digits(value):
    if value is None:
        return ""
    return _to_fa_digits(str(value))


@register.filter
def rate_source_fa(value):
    labels = {"nobitex": "نوبیتکس", "manual": "دستی", "fallback": "حالت پشتیبان"}
    key = (value or "").lower() if isinstance(value, str) else ""
    return labels.get(key, "منبع نامشخص")


@register.filter
def rate_type_fa(value):
    labels = {
        "vwap": "میانگین وزنی دفتر سفارش",
        "best_ask": "پیشنهاد فروش",
        "legacy": "محاسبه ساده",
    }
    key = (value or "").lower() if isinstance(value, str) else ""
    return labels.get(key, "نوع نرخ نامشخص")


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
        return _to_fa_digits(f"{int(value):,}".replace(",", "٬"))
    except (TypeError, ValueError):
        return "۰"


@register.filter
def jalali_datetime(value):
    if not value:
        return "—"
    return jalali_datetime_string(value)


@register.filter
def jalali_date(value):
    if not value:
        return "—"
    return jalali_date_string(value)


@register.filter
def jalali_input(value):
    return jalali_datetime_input(value)


@register.filter
def campaign_status_label(code: str) -> str:
    from apps.campaigns.models import Campaign

    try:
        return Campaign.Status(code).label
    except (ValueError, TypeError):
        return "وضعیت نامشخص"


_TELEGRAM_REMOTE_STATUS_FA = {
    "active": "فعال در تلگرام",
    "on_hold": "در انتظار",
    "stopped": "متوقف‌شده",
    "paused": "متوقف‌شده",
    "declined": "ردشده توسط تلگرام",
    "rejected": "ردشده توسط تلگرام",
    "in_review": "در حال بررسی تلگرام",
    "pending": "در انتظار بررسی",
    "ready_for_review": "آماده بررسی",
    "approved": "تأییدشده",
    "completed": "تکمیل‌شده",
    "failed": "ناموفق",
    "cancelled": "لغوشده",
}


@register.filter
def telegram_remote_status_fa(value):
    key = str(value or "").strip().lower()
    if not key:
        return "—"
    return _TELEGRAM_REMOTE_STATUS_FA.get(key, "وضعیت نامشخص")


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
        number = float(value)
        text = f"{number:,.4f}".rstrip("0").rstrip(".").replace(",", "٬")
        return _to_fa_digits(text)
    except (TypeError, ValueError):
        return "—"


@register.filter
def format_count(value):
    try:
        return _to_fa_digits(f"{int(value):,}".replace(",", "٬"))
    except (TypeError, ValueError):
        return "—"


@register.filter
def shorten_url(value, max_len=28):
    if not value:
        return "—"
    text = str(value).replace("https://", "").replace("http://", "")
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


@register.filter
def tabular(value):
    return value


_CURRENCY_LABELS_FA = {
    "TON": "تون",
    "GRAM": "گرام",
    "XTR": "استار تلگرام",
    "EUR": "یورو",
    "USD": "دلار آمریکا",
    "IRR": "ریال",
    "RLS": "ریال",
    "TOMAN": "تومان",
}


@register.filter
def currency_label_fa(value):
    return _CURRENCY_LABELS_FA.get(str(value or "").strip().upper(), "واحد نامشخص")


_TELEGRAM_FEATURE_LABELS_FA = {
    "account.read": "اطلاعات حساب",
    "account.info": "جزئیات حساب",
    "account.related": "حساب‌های مرتبط",
    "account.transactions": "تراکنش‌های حساب",
    "account.stats": "آمار حساب",
    "account.report": "گزارش حساب",
    "audiences.list": "فهرست مخاطبان",
    "pixel.events": "رویدادهای پیکسل",
    "pixel.read": "اطلاعات پیکسل",
    "ads.list": "فهرست تبلیغات",
    "ads.get": "جزئیات تبلیغ",
    "ads.stats": "آمار تبلیغ",
    "ads.transactions": "تراکنش‌های تبلیغ",
    "targeting.languages": "زبان‌های هدف‌گیری",
    "targeting.topics": "موضوعات هدف‌گیری",
    "targeting.countries": "کشورهای هدف‌گیری",
    "targeting.bot": "بررسی ربات هدف",
    "ads.create": "ساخت تبلیغ",
    "ads.edit": "ویرایش تبلیغ",
    "ads.submit_review": "ارسال تبلیغ برای بررسی",
    "ads.delete": "حذف تبلیغ",
    "media.upload_photo": "بارگذاری تصویر",
    "media.upload_video": "بارگذاری ویدیو",
    "media.website_photo": "تصویر وب‌سایت",
    "ads.budget_increase": "افزایش بودجه تبلیغ",
    "ads.budget_decrease": "کاهش بودجه تبلیغ",
    "account.create": "ایجاد حساب",
    "account.budget_increase": "افزایش اعتبار حساب",
    "account.budget_decrease": "کاهش اعتبار حساب",
    "audiences.create": "ایجاد گروه مخاطبان",
    "audiences.edit": "ویرایش گروه مخاطبان",
    "audiences.delete": "حذف گروه مخاطبان",
    "pixel.create": "ایجاد پیکسل",
    "pixel.event_create": "ایجاد رویداد",
    "pixel.event_edit": "ویرایش رویداد",
    "pixel.event_delete": "حذف رویداد",
}


@register.filter
def telegram_feature_label_fa(value):
    return _TELEGRAM_FEATURE_LABELS_FA.get(str(value or ""), "قابلیت دیگر")


_TELEGRAM_REASON_LABELS_FA = {
    "no_linked_ad_for_probe": "برای بررسی این قابلیت، تبلیغ متصلی در حساب وجود ندارد.",
    "network_or_configuration_unavailable": "اتصال یا تنظیمات سرویس در دسترس نیست.",
    "api_status_unverified": "وضعیت این قابلیت هنوز تأیید نشده است.",
    "probe_failed": "بررسی قابلیت با خطا روبه‌رو شد.",
    "telegram_api_response": "پاسخ سرویس تلگرام نیازمند بررسی است.",
    "write_disabled_by_tmads_not_api_capability": "این عملیات به دلایل ایمنی در سامانه غیرفعال است.",
    "write_not_probed_for_safety": "این عملیات برای جلوگیری از تغییر ناخواسته آزمایش نشده است.",
    "ACCESS_DENIED": "دسترسی به این قابلیت از طرف تلگرام مجاز نیست.",
    "PERMISSION_DENIED": "مجوز لازم برای این قابلیت وجود ندارد.",
    "TOKEN_INVALID": "اطلاعات اتصال معتبر نیست.",
    "TOKEN_EXPIRED": "اعتبار اطلاعات اتصال به پایان رسیده است.",
    "AUTH_KEY_INVALID": "اطلاعات احراز هویت معتبر نیست.",
}


@register.filter
def telegram_error_fa(value):
    text = str(value or "").strip()
    if not text:
        return "—"
    if not re.search(r"[A-Za-z]{3,}", text):
        return text
    return _TELEGRAM_REASON_LABELS_FA.get(
        text,
        "جزئیات فنی برای بررسی مدیر سامانه در سوابق ثبت شده است.",
    )


_TELEGRAM_EVENT_LABELS_FA = {
    "page_view": "مشاهده صفحه",
    "add_to_cart": "افزودن به سبد خرید",
    "add_to_wishlist": "افزودن به علاقه‌مندی‌ها",
    "customize_product": "سفارشی‌سازی محصول",
    "initiate_checkout": "آغاز فرایند پرداخت",
    "add_payment_info": "ثبت اطلاعات پرداخت",
    "purchase": "خرید",
    "contact": "تماس",
    "lead": "ثبت سرنخ",
    "schedule": "رزرو زمان",
    "complete_registration": "تکمیل ثبت‌نام",
    "submit_application": "ارسال درخواست",
    "start_trial": "شروع دوره آزمایشی",
    "subscribe": "اشتراک",
    "view_content": "مشاهده محتوا",
    "search": "جستجو",
    "find_location": "یافتن موقعیت",
    "donate": "کمک مالی",
    "custom": "رویداد سفارشی",
}


@register.filter
def telegram_event_type_fa(value):
    return _TELEGRAM_EVENT_LABELS_FA.get(str(value or ""), "رویداد دیگر")


_ASSET_ACTION_LABELS_FA = {
    "audience": "ایجاد گروه مخاطبان",
    "pixel": "ایجاد پیکسل",
    "event": "ایجاد رویداد",
    "audience_add": "افزودن اعضای مخاطبان",
    "audience_remove": "حذف اعضای مخاطبان",
    "audience_delete": "حذف گروه مخاطبان",
    "audience_reset": "خالی‌کردن گروه مخاطبان",
    "event_rename": "تغییر عنوان رویداد",
    "event_delete": "حذف رویداد",
}


@register.filter
def asset_operation_label_fa(value):
    return _ASSET_ACTION_LABELS_FA.get(str(value or ""), "عملیات منابع حساب")


_AUDIT_ACTION_LABELS_FA = {
    "exchange_rate.manual": "ثبت نرخ دستی",
    "ops.approve": "تأیید کمپین",
    "ops.reject": "رد کمپین",
    "ops.rerun_policy": "بررسی دوباره قوانین",
    "ops.submit_telegram": "ارسال تبلیغ به تلگرام",
    "ops.settle_allocation": "تطبیق و تسویه اعتبار",
    "ops.link_ad": "بررسی اتصال تبلیغ",
}


@register.filter
def audit_action_fa(value):
    return _AUDIT_ACTION_LABELS_FA.get(str(value or ""), "عملیات مدیریتی")


_ENTITY_TYPE_LABELS_FA = {
    "campaign": "کمپین",
    "Campaign": "کمپین",
    "ExchangeRate": "نرخ ارز",
    "RefundRequest": "درخواست بازپرداخت",
    "AdvertisingOrder": "سفارش تبلیغ",
    "CustomerProfile": "حساب مشتری",
    "Wallet": "کیف پول",
    "RelatedAccountRequest": "درخواست حساب مرتبط",
}


@register.filter
def audit_entity_type_fa(value):
    return _ENTITY_TYPE_LABELS_FA.get(str(value or ""), "مورد ثبت‌شده")


_OPERATION_PAYLOAD_LABELS_FA = {
    "amount_ton": "مقدار اعتبار (تون)",
    "amount": "مبلغ",
    "budget": "بودجه",
    "daily_cap_ton": "سقف روزانه (تون)",
    "daily_limit": "سقف روزانه",
    "cpm": "هزینه هر هزار نمایش",
    "status": "وضعیت",
    "is_paused": "وضعیت توقف",
    "title": "عنوان",
    "name": "نام",
    "start_date": "تاریخ آغاز",
    "end_date": "تاریخ پایان",
    "schedule_start": "زمان آغاز",
    "schedule_end": "زمان پایان",
    "placement": "جایگاه نمایش",
    "target_type": "نوع هدف‌گیری",
}


@register.filter
def operation_payload_label_fa(value):
    return _OPERATION_PAYLOAD_LABELS_FA.get(str(value or ""), "")


@register.filter
def operation_value_fa(value):
    if isinstance(value, bool):
        return "بله" if value else "خیر"
    if isinstance(value, (int, float)):
        return _to_fa_digits(value)
    key = str(value or "").strip().lower()
    labels = {
        "active": "فعال",
        "paused": "متوقف",
        "on_hold": "در انتظار",
        "pending": "در انتظار بررسی",
        "completed": "تکمیل‌شده",
        "failed": "ناموفق",
        "approved": "تأییدشده",
        "rejected": "ردشده",
        "true": "بله",
        "false": "خیر",
        "ton": "تون",
        "eur": "یورو",
        "usd": "دلار آمریکا",
        "xtr": "استار تلگرام",
    }
    if re.search(r"[A-Za-z]{3,}", str(value or "")):
        return labels.get(key, "جزئیات ثبت‌شده")
    return labels.get(key, value)


@register.filter
def sms_error_fa(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if not re.search(r"[A-Za-z]{3,}", text):
        return text
    labels = {
        "insufficient_credit": "اعتبار پنل پیامک کافی نیست.",
        "invalid_phone": "شماره گیرنده معتبر نیست.",
        "invalid_api_key": "دسترسی پنل پیامک معتبر نیست.",
        "timeout": "پاسخ پنل پیامک به‌موقع دریافت نشد.",
        "connection_error": "ارتباط با پنل پیامک برقرار نشد.",
    }
    return labels.get(text.lower(), "خطای فنی ثبت شده است؛ برای پیگیری با پشتیبانی فنی تماس بگیرید.")


@register.filter
def sms_provider_fa(value):
    return "فراز اس‌ام‌اس" if str(value or "").strip().lower() == "faraz" else "پنل پیامک"


@register.filter
def telegram_peer_type_fa(value):
    labels = {
        "user": "کاربر",
        "channel": "کانال",
        "chat": "گفتگو",
        "account": "حساب",
        "advertiser": "تبلیغ‌دهنده",
    }
    return labels.get(str(value or "").lower(), "طرف تراکنش نامشخص")


@register.filter
def telegram_transfer_status_fa(value):
    labels = {
        "completed": "تکمیل‌شده",
        "success": "موفق",
        "pending": "در انتظار",
        "processing": "در حال پردازش",
        "failed": "ناموفق",
        "rejected": "ردشده",
        "cancelled": "لغوشده",
    }
    return labels.get(str(value or "").lower(), "وضعیت نامشخص")


@register.filter
def user_message_fa(value):
    text = str(value or "").strip()
    if not text:
        return ""
    if re.search(r"[A-Za-z]{3,}", text):
        return "جزئیات فنی در سوابق سامانه ثبت شده است؛ برای پیگیری با پشتیبانی فنی تماس بگیرید."
    return text
