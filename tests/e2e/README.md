# Playwright E2E (اجرای دستی — خارج از CI پیش‌فرض)

پس از نصب Playwright در محیط مجاز:

```powershell
cd D:\MYROBOTS\TMADS
npm init -y
npm install -D @playwright/test
npx playwright install chromium
```

اجرای پیشنهادی (نیازمند سرور Django در حال اجرا و احراز هویت تست):

```powershell
$env:DJANGO_SETTINGS_MODULE="config.settings.local"
.\.venv\Scripts\python.exe manage.py runserver 8000
# ترمینال دیگر:
npx playwright test --project=chromium
```

سناریوهای پیشنهادی: ویزارد ۵ مرحله، سوییچ simple/pro، گرید زمان‌بندی، selector کشور، checkout کیف پول.

Viewports: 390×844, 768×1024, 1440×900
