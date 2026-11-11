# حساب مرکزی عملیاتی (Hyper Tunnel)

در محیط فعلی اپراتور، تبلیغات ثبت‌شده در [Telegram Ads](https://ads.telegram.org) زیر حساب مرکزی هستند و همگی مقصد **ربات Hyper Tunnel** دارند (`t.me/HyperTunnelbot`).

در TMADS این کمپین‌ها به **سوپر‌یوزر / پروفایل مشتری متناظر** نسبت داده می‌شوند (مدل Central account + customer isolation).

## همگام‌سازی از API

```bash
python manage.py import_telegram_campaigns --prune-drafts
```

- کمپین‌های ریموت را با نام، مقصد، وضعیت و آمار خلاصه می‌سازد یا به‌روز می‌کند.
- `--prune-drafts` پیش‌نویس‌های تست محلی («کمپین جدید») را که به تلگرام وصل نیستند حذف می‌کند.
- `--username` برای مالک غیر از اولین سوپر‌یوزر.

پس از لینک، `sync_telegram_ads` و تسک‌های Celery آمار را به‌روز نگه می‌دارند.

**امنیت:** توکن `TELEGRAM_ADS_API_TOKEN` را هرگز commit نکنید؛ در صورت لو رفتن در مخزن، توکن را در پنل تلگرام باطل و جایگزین کنید.
