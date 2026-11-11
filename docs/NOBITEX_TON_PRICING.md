# Nobitex TON (Gram) Pricing Engine

## نکته بازار

در Telegram Ads واحد پولی **Gram (گرام)** همان **TON (تون)** است — نه «گرم» (دما). در نوبیتکس نماد معاملاتی **`gram`** (نه `ton`) است:

| API | مقدار |
|-----|--------|
| Market stats | `GET /market/stats?srcCurrency=gram&dstCurrency=rls` → کلید `gram-rls` |
| Order book | `GET /v3/orderbook/GRAMIRT` |

قیمت‌ها بر حسب **ریال (RLS/IRR)** به ازای هر **گرام** هستند.

## Endpoints (read-only)

- آمار بازار: `https://apiv2.nobitex.ir/market/stats`
- دفتر سفارش: `https://apiv2.nobitex.ir/v3/orderbook/GRAMIRT`

بدون توکن. بدون سفارش خرید/فروش.

## منطق نرخ

1. **Base rate** = `bestSell` (Best Ask) از stats — مرجع خرید.
2. برای حجم مشخص: **VWAP** روی سمت `asks` در order book.
3. اگر عمق کافی نباشد: `InsufficientLiquidityError` و توقف Quote.

## Lifetime vs Quote

- KPI تبلیغ تلگرام جداست (Nobitex فقط نرخ تهیه TON).
- **Quote** = بودجه تبلیغ IRR + کارمزد + بافر ریسک.
- اعتبار Quote: `QUOTE_VALIDITY_SECONDS` (پیش‌فرض ۳۰۰).
- پرداخت با Quote منقضی یا `locked_total` ناهمخوان مسدود است.

## تومان / ریال

`1 Toman = 10 IRR` — ذخیره داخلی integer IRR.

## Env

```env
NOBITEX_STATS_SRC_CURRENCY=gram
NOBITEX_STATS_DST_CURRENCY=rls
NOBITEX_STATS_PAIR=gram-rls
NOBITEX_ORDERBOOK_SYMBOL=GRAMIRT
NOBITEX_MAX_RATE_AGE_SECONDS=180
QUOTE_VALIDITY_SECONDS=300
TON_PRICING_RISK_BUFFER_PERCENT=2
```

## Celery

`apps.finance.tasks.refresh_ton_exchange_rate` — هر ۶۰ثانیه در `CELERY_BEAT_SCHEDULE`.

## دستورات

```bash
python manage.py refresh_ton_rate
python manage.py setup_beat
```

## Ops

`/ops/exchange-rates/` — نمایش زنده، refresh دستی، override مدیر با audit.

## تست

`pytest tests/test_nobitex_pricing.py` — Mock-only، بدون معامله واقعی.
