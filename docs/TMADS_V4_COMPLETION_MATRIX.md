# TMADS V4 — ماتریس تکمیل (آخرین به‌روزرسانی: 2026-11-11)

## Baseline (فاز ۰)

| بررسی | نتیجه |
|--------|--------|
| `manage.py check` | بدون خطا |
| `makemigrations --check` | بدون migration معلق |
| `pytest` | **64 passed** (پس از V4؛ پیش از این گزارش 56 بود) |
| Git | مخزن git در مسیر پروژه یافت نشد |
| `TELEGRAM_ADS_WRITE_ENABLED` | باید `false` بماند |
| مجوز اپراتور | بدون bypass؛ پیش‌فرض `pending` |

---

## ماتریس ویژگی‌ها

| حوزه | وضعیت | توضیح |
|------|--------|--------|
| **حالت ساده / حرفه‌ای** | تکمیل شده (MVP+) | سوییچ در ویزارد؛ داده حفظ می‌شود؛ فیلدهای `studio-pro-only` در حالت ساده مخفی |
| **Search targeting** | تکمیل شده | چیپ عبارت، paste/split، حد ۱۰، dry-run تست‌شده |
| **Bots targeting** | تکمیل جزئی→قابل استفاده | چیپ + نرمال‌سازی URL؛ resolve از API در صورت اتصال |
| **Users targeting** | تکمیل جزئی→قابل استفاده | انتخابگر کشور/موضوع/زبان از کاتالوگ؛ جستجوی شهر وابسته به کشور |
| **Channels targeting** | تکمیل جزئی→قابل استفاده | حالت language/topics/specific؛ انتخابگر زبان/موضوع؛ چیپ کانال |
| **کاتالوگ API** | تکمیل شده (gated) | کش Redis/Django cache؛ fallback آفلاین؛ بدون write |
| **زمان‌بندی هفتگی** | تکمیل شده | گرید ۷×۲۴، timezone ایران 12600s، `InputAdSchedule.validate` در payload |
| **تاریخ شمسی نمایش** | تکمیل جزئی | `jalali_datetime` در مرحله بودجه؛ ورودی هنوز `datetime-local` گرگوری |
| **آپلود رسانه محلی** | تکمیل جزئی | JPEG/PNG/WebP/MP4 + Pillow/imghdr؛ آپلود تلگرام gated |
| **پیش‌نمایش خلاقه** | قبلاً موجود | `studio_preview.html` |
| **Autosave / conflict** | قبلاً موجود | ۱.۸s debounce + revision 409 |
| **Policy در ویزارد** | تکمیل شده | پنل + دکمه «بررسی مجدد» AJAX (rate limit 3s) |
| **پرداخت / quote** | قبلاً موجود | تست‌های finance/campaign_flow |
| **Dry-run createAd** | تکمیل شده | هر ۴ نوع هدف در `test_v4_studio_journeys.py` |
| **Ops center** | جزئی | `campaign_review` موجود؛ preflight UI بهبود محدود در این فاز |
| **Playwright E2E** | آماده‌سازی | اسکلت در `tests/e2e/README.md` — اجرا نشده |

---

## چهار روش هدف‌گیری — فیلدهای فعال

### Search
- عبارت‌های جستجو (JSON/chips)
- placement ثابت `search_result`
- بدون متن اسپانسری در payload
- promote URL

### Bots
- `bot_ids[]` با @username
- متن ۱–۱۶۰، CPM، بودجه
- placement `bot_banner`

### Users
- کشورها، شهرها (location_id)، موضوعات، زبان (pro)، device (pro)
- placement سازگار
- schedule اختیاری

### Channels
- `channel_mode`، زبان‌ها، topic IDs، کانال مشخص، مستثنی‌ها
- قواعد انحصار موضوع/زبان در validators

---

## تست‌ها

```
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe -m pytest -q
```

فایل‌های جدید مهم: `tests/test_v4_studio_journeys.py`, `tests/test_schedule_utils.py`

---

## Production blockers (خارج از کد)

- موجودی TON حساب عملیات
- `TELEGRAM_ADS_WRITE_ENABLED` و تأیید زنده API
- `OperatorAdvertisingAuthorization` واقعی (نه صوری)
- زرین‌پال production
- QA مرورگر (390/768/1440)
- استقرار production

---

## فایل‌های تغییر یافته در فاز V4

- `apps/campaigns/schedule_utils.py`, `catalog.py`, `media_validation.py`
- `apps/campaigns/studio.py`, `views.py`, `urls.py`
- `apps/telegram_ads/services/ad_payload.py`
- `templates/campaigns/wizard.html`, `includes/schedule_grid.html`, `includes/policy_panel.html`
- `static/js/ad-studio.js`, `static/css/design-executive.css`
- `tests/test_v4_studio_journeys.py`, `tests/test_schedule_utils.py`
