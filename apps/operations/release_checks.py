"""Fail-closed production readiness checks without secrets or API writes.

A code implementation cannot prove third-party permission, live settlement,
payment reconciliation or browser QA. Explicit external verification stays
pending even when local configuration passes.
"""
from dataclasses import dataclass, asdict

from django.conf import settings

from apps.policies.models import OperatorAdvertisingAuthorization


@dataclass(frozen=True)
class ReleaseCheck:
    key: str
    label: str
    state: str  # ready / blocked / pending
    explanation: str

    def as_dict(self):
        return asdict(self)


def release_checks():
    checks = []
    def add(key, label, valid, detail, *, pending=False):
        checks.append(ReleaseCheck(
            key=key, label=label,
            state="pending" if pending else "ready" if valid else "blocked",
            explanation=detail,
        ))

    current = OperatorAdvertisingAuthorization.objects.filter(is_current=True).order_by("-id").first()
    approved = bool(
        current and current.state == "approved" and current.documented_basis.strip()
        and current.reviewed_at and current.reviewed_by_id
    )
    add("operator_authorization", "مجوز تبلیغات از طریق حساب مرکزی", approved,
        "تأیید معتبر مستند و بررسی‌شده برای حساب مرکزی لازم است؛ وضعیت پیش‌فرض کافی نیست.")
    production = str(getattr(settings, "APP_ENV", "")).upper() == "PRODUCTION"
    secure = bool(
        production and settings.DEBUG is False and settings.SESSION_COOKIE_SECURE
        and settings.CSRF_COOKIE_SECURE and settings.SECURE_SSL_REDIRECT
        and settings.SECURE_HSTS_SECONDS >= 31536000
        and settings.ALLOWED_HOSTS and not any("*" in host for host in settings.ALLOWED_HOSTS)
    )
    add("settings", "تنظیمات ایمن محیط تولید", secure,
        "محیط Production، HTTPS، HSTS، کوکی امن و ALLOWED_HOSTS محدود بررسی می‌شود.")
    postgres = settings.DATABASES.get("default", {}).get("ENGINE") == "django.db.backends.postgresql"
    add("database", "پایگاه داده PostgreSQL", postgres,
        "برای استقرار تجاری پایگاه داده PostgreSQL و پشتیبان‌گیری مستقل لازم است.")
    payment = bool(
        not settings.PAYMENT_FAKE_ENABLED and (
            (settings.PAYMENT_GATEWAY == "zarinpal" and not settings.ZARINPAL_SANDBOX and settings.ZARINPAL_MERCHANT_ID)
            or (settings.PAYMENT_GATEWAY == "zibal" and settings.ZIBAL_MERCHANT_ID.strip()
                and settings.ZIBAL_MERCHANT_ID.strip().lower() != "zibal")
        )
    )
    add("payment", "اتصال تولیدی درگاه پرداخت", payment,
        "تأیید اعتبار تنظیمات فقط شرط اولیه است؛ تراکنش‌های آزمایشی واقعی جداگانه باید تأیید شوند.")
    from apps.notifications.faraz import configured
    add("sms_config", "تنظیمات پیامک فراز", bool(settings.SMS_PROVIDER == "faraz" and all(
        configured(purpose) for purpose in settings.FARAZSMS_PATTERNS)),
        "کلید، خطوط و پترن‌های مستقل بررسی می‌شوند؛ ارسال واقعی نیازمند آزمون است.")
    add("sms_live", "آزمون ارسال و دریافت پیامک", False, "تحویل پیامک و عملکرد صف باید در محیط واقعی آزموده شود.", pending=True)
    token = bool(settings.TELEGRAM_ADS_API_TOKEN)
    add("telegram_token", "توکن API تبلیغات", token,
        "صرفاً وجود توکن بررسی می‌شود؛ مقدار، بخشی از آن یا شناسه قابل بازیابی نمایش داده نمی‌شود.")
    writes = bool(settings.TELEGRAM_ADS_WRITE_ENABLED and settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED)
    add("live_submission", "گیت ارسال واقعی تبلیغ", writes and approved,
        "فعال‌سازی ارسال فقط پس از مجوز معتبر و تست‌های ایمن مجاز است.")
    # These cannot be certified solely from settings or repository state.
    add("integration_tests", "تست مالی و تلگرام در محیط آزمایشی", False,
        "نتیجه تست تراکنش، بازپرداخت، مجوزها و API باید مستقل ثبت شود.", pending=True)
    add("browser_qa", "تأیید بصری و دسترس‌پذیری", False,
        "نتیجه تست واقعی در موبایل، تبلت و دسکتاپ ثبت نشده است.", pending=True)
    add("account_routing", "تفکیک مالی و تبلیغاتی حساب‌های زیرمجموعه", False,
        "مسیردهی کمپین به حساب اختصاصی و تسویه اعتبار زیرحساب هنوز تکمیل نشده است.", pending=True)
    return checks


def readiness_summary():
    checks = release_checks()
    return {
        "items": checks,
        "ready": sum(x.state == "ready" for x in checks),
        "blocked": sum(x.state == "blocked" for x in checks),
        "pending": sum(x.state == "pending" for x in checks),
        "can_launch": all(x.state == "ready" for x in checks),
    }
