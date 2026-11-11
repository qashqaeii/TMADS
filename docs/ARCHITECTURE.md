# Architecture summary

## Tenancy

- `CustomerProfile` 1:1 `User` (role `customer`)
- All business entities include `customer` FK or are reachable only through owned campaigns
- Remote `TelegramAdvertisement.remote_ad_id` is never used for authorization

## Financial model

- Stored amounts: **integer IRR**
- Display: Toman = IRR / 10
- Wallet: `available_irr`, `reserved_irr`
- Immutable `WalletLedgerEntry` with idempotency keys

## Campaign flow

1. Wizard draft (`Campaign.wizard_data`, step autosave on POST)
2. Quote (`AdvertisingOrder`, `PriceQuote`, 2h expiry placeholder)
3. Payment/reservation from wallet (sandbox top-up available)
4. Ops submission to Telegram Ads API (gated)

## Integration layer

`apps.telegram_ads.client.TelegramAdsClient` wraps `telead`, with write gates in settings.

## Frontend

Django templates, RTL (`lang=fa dir=rtl`), design tokens in `static/css/app.css`, HTMX/Alpine for light interactivity.

## Refunds

Customer `RefundRequest` on paid pre-launch orders; ops approval releases wallet reservation via ledger idempotency keys.

## Payments

`FakeGateway` (LOCAL) and `ZarinpalGateway` (v4 request/verify, Toman amounts). Callback route: `finance:topup_callback`.

## Legal copy

Editable Markdown in `docs/legal/*.md`, rendered on public legal pages.

## Not verified in this build

- Live Zarinpal with production merchant + bank settlement
- Telegram Ads write/create on production account
- Playwright UI smoke tests (URL smoke via pytest instead)
