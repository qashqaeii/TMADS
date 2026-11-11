# Telegram Ads Policy Mapping (TMADS)

**آخرین بازبینی:** 2025-11-11  
**نسخه داخلی:** `2025-11-11-tmads-1`

> خلاصه‌های فارسی در این سند راهنمای عملی TMADS هستند. متن رسمی [Telegram Ad Guidelines](https://ads.telegram.org/guidelines) و [Telegram Ad Platform ToS](https://ads.telegram.org/tos) مرجع حقوقی است.

| Rule ID | منبع | بند | URL | اجرای خودکار | بررسی انسانی | شدت پیش‌فرض | پیام کاربر (نمونه) |
|---------|------|-----|-----|--------------|--------------|-------------|-------------------|
| TG-FMT-001 | Guidelines | §1 طول متن ۱۶۰ کاراکتر | https://ads.telegram.org/guidelines | بله | خیر | BLOCKED | متن تبلیغ از سقف مجاز بیشتر است |
| TG-EDI-002 | Guidelines | §2 ویرایشی (خط جدید، لیست، اغراق) | همان | جزئی | بله | WARNING/BLOCKED | متن باید در یک خط باشد |
| TG-LNK-003 | Guidelines | §3 فرمت لینک | همان | بله | خیر | BLOCKED | بیش از یک لینک در متن مجاز نیست |
| TG-DST-004 | Guidelines | §4 مقصد و هدف‌گیری | همان | جزئی | بله | WARNING/REVIEW | کانال باید در ۱۴ روز اخیر پست داشته باشد |
| TG-PRH-005 | Guidelines | §5.1–5.12 محتوای ممنوع | همان | راهنما (کلیدواژه) | بله | REVIEW_REQUIRED | موضوع حساس — نیازمند بررسی |
| TG-TOS-006 | Ads ToS | §3.3(e) ممنوعیت پیشنهاد از طرف شخص ثالث | https://ads.telegram.org/tos | بله (درگاه اپراتور) | بله | BLOCKED | مجوز حساب مرکزی تأیید نشده |
| TG-TOS-007 | Ads ToS | §4.3 اعتبار غیرقابل برداشت تلگرام | همان | خیر (UX) | خیر | INFO | تفاوت کیف TMADS و اعتبار تلگرام |
| TG-GSG-008 | Getting Started | مقصد t.me در راهنمای عمومی | https://ads.telegram.org/getting-started | بله | بله | REVIEW | مقصد وب نیازمند تأیید قالب/API |
| TMADS-ACC-001 | TMADS Terms | پذیرش مشتری | /terms/ | بله | خیر | BLOCKED (strict) | پذیرش قوانین الزامی است |

## پوشش تست خودکار

| Rule ID | فایل تست |
|---------|----------|
| TG-FMT-001 | `tests/test_policies.py::test_text_length_blocked` |
| TG-EDI-002 | `tests/test_policies.py::test_line_break_blocked` |
| TG-LNK-003 | `tests/test_policies.py::test_multiple_text_links_blocked`, `test_link_mismatch_blocked` |
| TG-TOS-006 | `tests/test_policies.py::test_submission_blocked_without_operator_gate` |

## موارد غیرقابل تأیید خودکار (UNKNOWN / اعلامی)

- تست تعامل خصوصی ربات در همه حالت‌ها
- فعالیت واقعی کانال بدون API عمومی معتبر
- قصد واقعی تبلیغ در بستر آموزشی/انتقادی
- تطابق زبان مقصد با زبان هدف‌گیری (کشف محدود)

## هدف‌گیری بر اساس نوع Target

| Target | قوانین اصلی |
|--------|-------------|
| search | TG-DST-004 (§4.8 keywords), TG-PRH-005 |
| bots | TG-FMT-001, TG-DST-004 (ربات), TG-LNK-003 |
| users | TG-FMT-001, TG-DST-004, رسانه (API alignment) |
| channels | TG-FMT-001, TG-DST-004 (کانال §4.5), رسانه |
