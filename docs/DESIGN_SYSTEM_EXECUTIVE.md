# Telegram Executive Blue

Design system برای TMADS — Quiet Luxury، Telegram-inspired، FinTech SaaS، RTL-first.

## بارگذاری

- `static/css/app.css` — ساختار پایه
- `static/css/design-executive.css` — توکن‌ها و لایه Executive (اصلی)

## KPI

از `kpi-exec` / `kpi-exec-grid` و `includes/kpi_icon.html` استفاده کنید.

## نمودارها

- نمایش: `#2AABEE`
- کلیک: `#177DC7`
- اکشن: `#16866A`
- هزینه: `#7D8FA5`

## دسترسی

دکمه‌ها `focus-visible` با حلقه آبی برند. `prefers-reduced-motion` رعایت شده.

## Motion

- `static/js/motion.js` — stagger + scroll reveal
- توکن‌ها و micro-interaction در `design-executive.css`
- KPI: ورود scale-in با تأخیر پله‌ای؛ کارت‌ها با reveal هنگام اسکرول

## الگوی صفحه (اپ)

1. `app_shell.html` یک `page-frame` بیرونی دارد.
2. هر view: `<div class="app-stack">` + `{% include "includes/dash_header.html" %}` + محتوا.
3. هدر غنی (مثلاً جزئیات کمپین): کلاس‌های `dash-header--rich` / `dash-header--with-sub` روی markup اختصاصی؛ اکشن‌های چندگانه در `dash-header__actions`.
4. `dash_header` برای دو CTA: `secondary_action_url` + `action_url` (+ `action_primary`).

## الگوی عمومی

- `public_base`: `site-header--exec`, `nav-bar--exec`, `site-footer--exec`
- صفحات داخلی: `public-hero` فشرده
- خانه: `hero--exec`, `steps-row--exec`, `section-head--exec`

## جزئیات کمپین

- `breadcrumb`, `detail-tabs`, `tab-bar` — override در `design-executive.css`
- تاریخچه وضعیت: `activity-feed` (نه timeline قدیمی)

لیست کامل صفحات: `docs/DESIGN_PAGES_AUDIT.md`

## فیلتر و جستجو (اپ)

الگوی استاندارد: `section.filter-exec-shell` → `form.filter-exec` → `div.filter-exec__grid`.

- کمپین‌ها: `filter-exec__grid--campaigns` (جستجو + وضعیت + جایگاه + اعمال/پاک کردن)
- فیلتر تک‌فیلدی Ops: `filter-exec__grid--inline`
- کلاس کنترل: `filter-exec__control` و برچسب `filter-exec__label`
- موبایل: ستونی تمام‌عرض، دکمهٔ اعمال در پایین
