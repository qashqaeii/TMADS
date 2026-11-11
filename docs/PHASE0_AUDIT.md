# Phase 0 — Repository Audit

**Date:** 2025-11-10  
**Workspace:** `d:\MYROBOTS\TMADS`

## Findings

| Area | Status |
|------|--------|
| Existing code | None — greenfield repository |
| Git | Not initialized (or empty working tree) |
| Django | Not present |
| Frontend tooling | Not present |
| Deployment | Not present |
| Secrets | None committed |

## Decisions

- **Project codename:** TMADS (Telegram Ads SaaS)
- **Django:** 5.2 LTS, Python 3.12+
- **Stack:** PostgreSQL, Redis, Celery, DRF (API where needed), Templates + Tailwind + HTMX + Alpine.js
- **Default safety:** `TELEGRAM_ADS_WRITE_ENABLED=false`, fake payment gateway in LOCAL
- **Central account model:** Customer isolation via tenant-scoped models and ownership checks

## Implementation checklist (phases)

- [x] Phase 0 — Audit (this document)
- [x] Phase 1 — Foundation (project, settings, auth, roles, base layout, Docker)
- [x] Phase 2 — Premium frontend (MVP: public site, dashboard shell, design tokens)
- [x] Phase 3 — Campaign engine (models, 8-step wizard, drafts, duplicate)
- [x] Phase 4 — Finance (wallet, ledger, orders, fake gateway top-up)
- [x] Phase 5 — Telegram Ads (telead client, read sync command, stats hook, Celery tasks)
- [x] Phase 6 — Administration (operations overview, campaigns, API status)
- [x] Phase 7 — Tests & polish (ECharts, premium UI tokens, jalali, 5 pytest)
- [x] Phase 8 — MVP complete (refunds ops flow, Zarinpal adapter, legal MD, wizard polish, admin, 10 pytest, setup_beat; production gateway/write verification remains operator-led)

## External dependencies (pending operator input)

- Production Iranian payment gateway credentials
- Fresh Telegram Ads API token (do not reuse exposed tokens)
- Legal/billing copy for Terms, Privacy, Refund
- Brand name and primary color (defaults provided)

## Telegram Ads compliance

Before public launch: verify central third-party advertising is permitted under the operator's Telegram Ads account terms.
