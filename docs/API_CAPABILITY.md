# API capability matrix (runtime)

Run:

```bash
python manage.py detect_capabilities
```

States: `supported`, `unsupported`, `permission_denied`, `unverified`, `temporary`.

| Feature key | Verified in MVP | Notes |
|-------------|-----------------|-------|
| `account.read` | Yes (with token) | `get_current_account` |
| `ads.list` | Yes (with token) | `get_ads_list` |
| `ads.create` | Gated | Requires `TELEGRAM_ADS_WRITE_ENABLED` + paid gate |

Observed placements in operator testing: `search_result`, `bot_banner` — enable in wizard only after account confirmation.
