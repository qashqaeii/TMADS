# MVP scope — delivered

## Customer

- Register / login / password reset / change password
- 8-step campaign wizard (choice grids, budget & schedule, wallet-aware payment)
- Wallet, fake or Zarinpal top-up, ledger, invoices
- Refund requests (pre-launch paid orders)
- Support tickets with campaign context
- Campaign detail, CSV export, duplicate

## Operations

- Campaign review queue, approve/reject, link remote ad ID, Telegram submit (write gated)
- Exchange rates, API status, audit log, refunds queue

## Integration

- `telead` read sync + Celery tasks + `setup_beat`
- Telegram write submission service (env gated)

## Out of MVP (operator / phase 2)

- Production Zarinpal settlement testing
- Live Telegram paid create on production account
- Playwright E2E
- Tailwind npm build pipeline (static design tokens in `app.css`)
