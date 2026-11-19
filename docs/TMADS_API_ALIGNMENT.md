# هم‌ترازی TMADS با Telegram Ads API

مرجع رسمی: [Telegram Ads API](https://ads.telegram.org/docs/api)  
نسخه محلی: `docs/Telegramads-API-INFORMATION.md`  
کتابخانه: `telead` — `apps.telegram_ads.client.TelegramAdsClient`

## اصول

| موضوع | TMADS |
|--------|--------|
| Lifetime metrics (Views, Spent, …) | فیلدهای شیء `Ad` در `TelegramAdvertisement.remote_status_raw` |
| Period metrics (نمودار روزانه) | `getAdStats` با `interval=86400` → `CampaignStatisticsSnapshot` با `raw.kind=period` |
| KPI پورتفولیو / لیست | **هرگز** جمع snapshotها برای lifetime — فقط از raw یا آخرین Ad |
| Write | فقط با `TELEGRAM_ADS_WRITE_ENABLED` و `TELEGRAM_ADS_PAID_SUBMISSION_ENABLED` |

## نگاشت placement

| API (`createAd`) | TMADS `Campaign.placement` |
|------------------|----------------------------|
| `search_result` | `search_result` |
| `bot_banner` | `bot_banner` |
| `channel_post` | `channels` |
| `video_banner` | `video` |

## متدهای پیاده‌سازی‌شده (خواندن)

| API | Client |
|-----|--------|
| getCurrentAccount | `get_account` |
| getAccountInfo | `get_account_info` |
| getAdsList | `list_advertisements` |
| getAdsById | `get_ad`, `get_ads_by_ids` |
| getAdStats | `get_ad_statistics(..., interval=86400)` |
| getAdTransactionsList | `get_ad_transactions` |
| getTargetLanguagesList | `get_target_languages` |
| getTargetTopicsList | `get_target_topics` |
| getTargetCountriesList | `get_target_countries` |
| getTargetBot | `resolve_target_bot` — `BOT_TOO_SMALL` → eligibility failure (read-only); see `docs/BOT_TARGET_ELIGIBILITY.md` |

## دستورات عملیاتی

```bash
python manage.py import_telegram_campaigns
python manage.py sync_telegram_ads
python manage.py detect_capabilities
```

صفحه: `/ops/api-status/` — حساب و قابلیت‌ها.

## وضعیت Ad (API → TMADS)

`stopped` / `on_hold` → paused · `active` → active · `declined` → rejected · `in_review` / `ready_for_review` → awaiting / pending review.

## کمپین‌های Hyper Tunnel

Import متمرکز: `docs/OPERATOR_ACCOUNT.md`. مالکیت customer سوپر‌یوزر حفظ می‌شود؛ حذف تبلیغ واقعی انجام نمی‌شود.

## خارج از scope فعلی (نیاز طراحی محصول)

- Audiences, Pixel / conversion_event_id کامل
- uploadAdPhoto / uploadAdVideo در ویزارد
- Related accounts و increaseAccountBudget
- submitAdForReview پس از فعال‌سازی write در staging
