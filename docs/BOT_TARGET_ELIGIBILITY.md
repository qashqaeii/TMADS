# Bot targeting eligibility (official API)

TMADS uses **only** the documented read method `getTargetBot` via `telead.Client.get_target_bot` / `TelegramAdsClient.resolve_target_bot`.

We do **not** call the Telegram Ads website private `searchBot` AJAX endpoint.

## Observed responses (staging account, read-only)

| Input | API `error` code | TMADS eligibility |
|--------|------------------|-------------------|
| `@vote`, `@gif`, `@BotFather` | — (success `TargetBot`) | `eligible` |
| `@IRTurboVpnBot`, `@HyperTunnelbot` | `BOT_TOO_SMALL` | `insufficient_audience` (hard block) |
| `@this_bot_definitely_not_exists_zzzzz` | `USERNAME_INVALID` | `invalid_bot` |
| `notvalid!!` | `BOT_ID_INVALID` | `invalid_bot` |

Success payload fields: `bot_id`, `title`, `username`, `photo_url` (no daily user count in the public object).

## Interpretation

- The **official public API** enforces the audience rule on read: failing bots return `BOT_TOO_SMALL` (maps to the website message about 1000+ daily users; TMADS does not parse or display exact counts).
- A **successful** `getTargetBot` returns metadata only; in practice Telegram rejects under-sized bots with an error instead of returning a peer, so success is treated as **verified eligible** for targeting.
- **Transport/timeouts** and **permission/token** failures are `api_unavailable` — never treated as ineligible.

## Diagnostic command

```powershell
python manage.py diagnose_target_bot @username another_bot --no-cache
```

No credentials are printed; token must exist in environment only.
