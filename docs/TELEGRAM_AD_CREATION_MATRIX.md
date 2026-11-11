# Telegram Ad Creation Matrix — TMADS V3

منابع: `docs/Telegramads-API-INFORMATION.md`، SDK نصب‌شده `telead`، حساب عملیات TMADS.

وضعیت‌های پیاده‌سازی: **Implemented** · **Conditional** · **N/A** · **Account unverified** · **Pending live verify**

## Legend placements

| API placement | Target types (verified) |
|---------------|-------------------------|
| `search_result` | `search` |
| `bot_banner` | `bots`, `users` |
| `channel_post` | `users`, `channels` |
| `video_banner` | `users` |

Engine: `apps/telegram_ads/targeting/compatibility.py`

---

## 1. Search (`target.type = search`)

| Dimension | Value |
|-----------|--------|
| Persian title | تبلیغات جستجوی تلگرام |
| Default placement | `search_result` |
| Ad text (`text`) | **N/A** — اختیاری/غیرضروری طبق API |
| Target object | `InputAdTargetSearch` · `search_queries` (max **10**) |
| Media photo/video | **N/A** |
| `show_userpic` | Conditional (برای مقصد bot/channel) |
| Preview | UI جستجو — Implemented |
| Draft incomplete | Implemented (بدون createAd) |
| Live createAd | Implemented پشت گیت — **not enabled in repo** |
| Implementation | **Implemented** (studio step 2 chips + validator) |

---

## 2. Bots (`target.type = bots`)

| Dimension | Value |
|-----------|--------|
| Persian title | تبلیغات در ربات‌ها |
| Placement | `bot_banner` |
| Required | `bot_ids` (≤100), `text`, `promote_url`, `cpm` |
| Target | `InputAdTargetBots` |
| Media | **N/A** per API for this target |
| Preview | Bot banner bubble — Implemented |
| Resolve bots | `getTargetBot` — client adapter Implemented (read) |
| Implementation | **Implemented** |

---

## 3. Users (`target.type = users`)

| Dimension | Value |
|-----------|--------|
| Persian title | هدف‌گیری کاربران |
| Placements | `channel_post`, `bot_banner`, `video_banner` |
| Target | `InputAdTargetUsers` |
| Countries | ≤8 ISO codes — Implemented (text input; catalogue API Conditional) |
| Locations | ≤20 · requires exactly 1 country — validator **Implemented** |
| Topics / exclude | ≤20 combined — Implemented |
| Channels / exclude | ≤100 combined — Implemented |
| Audiences | ≤10 combined — Conditional (UI placeholder / config keys) |
| Device | ios/android/mobile/desktop — Implemented |
| Political flags | Implemented in builder |
| Photo/video | Conditional — `channels`+`users` only in API |
| Catalog fetch | `getTargetCountriesList`, `getTargetLocationsList` — client methods Added |
| Implementation | **Implemented** (core fields); live catalogue UX **Conditional** |

---

## 4. Channels (`target.type = channels`)

| Dimension | Value |
|-----------|--------|
| Persian title | هدف‌گیری کانال‌ها |
| Placement | `channel_post` |
| Strategies | A language only · B topics+one language · C specific channels — **Implemented** (`channel_mode`) |
| Exclusions | exclude topics/channels — Implemented |
| Mutual exclusion | `channel_ids` vs `language_codes`/`topic_ids` — enforced via `telead.validate()` |
| Preview | Sponsored message — Implemented |
| Implementation | **Implemented** |

---

## Shared createAd fields (all targets)

| Official field | TMADS studio | Status |
|----------------|--------------|--------|
| title | campaign name | Implemented |
| promote_url | step 1/3 | Implemented |
| cpm | step 4 (Gram/TON) | Implemented |
| initial_budget | TON via Nobitex quote | Implemented |
| daily_budget_limit | daily cap Toman→TON | Implemented |
| impression_frequency 1–4 | seg control step 4 | Implemented |
| is_paused / initial status | on_hold vs active intent | Implemented |
| activate/deactivate dates | schedule_start/end | Implemented |
| schedule | `ad_settings.schedule` JSON | Conditional (storage ready; grid UI partial) |
| additional_info | step 4 | Implemented |
| show_userpic | step 3 | Implemented |
| photo_id / video_id | `ad_settings` | Conditional (upload gated) |
| website_* + button | `ad_settings` | Conditional |
| terms acceptance | step 5 | Implemented |
| conversion_event_id | `ad_settings` | Pending live verify |

---

## API write architecture

| Mode | Behavior |
|------|----------|
| LOCAL_DRAFT | DB only — **never** calls `createAd` |
| DRY_RUN | `dry_run_create_ad()` — payload + validation |
| LIVE | `execute_create_ad()` — requires `TELEGRAM_ADS_WRITE_ENABLED` + `TELEGRAM_ADS_PAID_SUBMISSION_ENABLED` |

Files: `apps/telegram_ads/services/ad_payload.py`, `ad_write.py`, `submission.py`

Idempotency: `idempotency_key` on create — Implemented

---

## Screenshot / official form parity (summary)

| UI area | Status |
|---------|--------|
| Four targeting tabs | Implemented as target cards step 1 |
| Search query chips | Implemented (JS + max 10) |
| Bot multi-select | Implemented (textarea @username) |
| User placement cards | Implemented |
| User countries/locations | Implemented basic; searchable selector **Conditional** |
| Channel three modes | Implemented |
| Weekly schedule grid | **Conditional** (API schedule object supported in payload) |
| Clear draft vs delete | Separate: save draft / delete draft campaign |
| Gram CPM label | Shown as Gram/TON secondary; Toman primary |

---

## Account / live blockers

- Live `createAd` / spend TON: **disabled** in `.env`
- Placement `video_banner` on operator account: **unverified** in `API_CAPABILITY.md`
- Full schedule UI + media upload to Telegram: **Pending live verify**
- Zarinpal production: unchanged operator blocker

---

## Tests

`tests/test_ad_creation_studio.py` — Search/Bots/Users/Channels payload, dry-run, autosave, mocked live create.
