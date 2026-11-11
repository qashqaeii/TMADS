# TMADS — Persian Telegram Advertising SaaS (MVP)

Production-oriented Django MVP with central Telegram Ads account, per-customer wallet (IRR), campaign wizard, and read-first API integration.

## Quick start (local, SQLite)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python manage.py migrate
python manage.py seed_demo
python manage.py createsuperuser
python manage.py runserver
```

- Health: `http://127.0.0.1:8000/health/`
- Public site: `/`
- Customer app: `/app/` (after register)
- Operations: `/ops/` (staff roles)

## Docker (PostgreSQL + Redis)

```bash
docker compose up -d db redis
# set DATABASE_URL in .env
python manage.py migrate
```

Profile `full` adds web, celery, beat.

## Telegram Ads

Set in `.env` (use a **new** token; never commit):

```
TELEGRAM_ADS_API_TOKEN=...
TELEGRAM_ADS_WRITE_ENABLED=false
TELEGRAM_ADS_PAID_SUBMISSION_ENABLED=false
```

Read-only sync & import:

```bash
python manage.py sync_telegram_ads
python manage.py import_telegram_campaigns
python manage.py detect_capabilities
```

See `docs/TMADS_API_ALIGNMENT.md` and `docs/Telegramads-API-INFORMATION.md`.

## TON / Rial pricing (Nobitex)

```bash
python manage.py refresh_ton_rate
```

Gram (Telegram TON) via Nobitex `gram-rls` / `GRAMIRT` — see `docs/NOBITEX_TON_PRICING.md`.

## Payments

`PAYMENT_GATEWAY=fake` for LOCAL. For Zarinpal sandbox/live set `PAYMENT_GATEWAY=zarinpal`, `ZARINPAL_MERCHANT_ID`, and `ZARINPAL_SANDBOX`.

Customer refunds: `/finance/refunds/` — ops queue: `/ops/refunds/`

## Operations (staff)

- `/ops/` overview
- `/ops/campaigns/` review queue — approve/reject/link remote ad ID / submit (write gated)
- `/ops/refunds/` approve wallet reservation releases
- `/ops/exchange-rates/` manual `irr_per_ton`
- `python manage.py detect_capabilities`
- `python manage.py setup_beat` — optional DB periodic tasks (Celery)

## Tests

```bash
pytest
python manage.py check
```

## Documentation

- `docs/PHASE0_AUDIT.md` — audit and phase checklist
- `docs/ARCHITECTURE.md` — architecture summary

## Safety defaults

- Write/paid submission disabled unless explicitly enabled in environment
- Customer data scoped by `customer` FK on all business models
- Separate internal UUIDs vs remote Telegram ad IDs
