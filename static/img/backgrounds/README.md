# TMADS — پس‌زمینه‌های Luxe

| فایل | نقش در UI |
|------|-----------|
| `tmads-bg-sidebar-dark.webp` | بدنهٔ سایدبار (موج آبی تیره عمودی) |
| `tmads-bg-sidebar-header.webp` | رزرو (فعلاً روی کل `aside` یکپارچه از `tmads-bg-sidebar-dark` استفاده می‌شود) |
| `tmads-bg-main-canvas.webp` | کانواس اصلی اپ (روشن، ابر و موج) |
| `tmads-bg-main-analytics.webp` | صفحات کمپین / تحلیل (خط روند روشن) |
| `tmads-bg-card-hero.webp` | کارت هیرو جزئیات کمپین و شل لیست |
| `tmads-bg-card-metrics.webp` | نوار KPI و کارت نمودار روند |

اتصال در `static/css/design-executive.css` (بخش TMADS background assets).

## GramAds workspace (2026)

- `gramads-dashboard-main-background.webp` — shared light-blue background of `main.app-content` for all internal workspace and operations pages.
- Connected by `static/css/gramads-workspace-background.css` and loaded after workspace composition via `templates/base.html`.
- Not used behind sidebar, topbar, login, or public marketing pages. Image is not applied to content cards, preserving readability.
- The obsolete canvas pseudo backgrounds are disabled for the internal workspace. Touch devices use scroll attachment instead of fixed.
