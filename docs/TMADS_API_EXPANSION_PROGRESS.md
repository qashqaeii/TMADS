# Telegram Ads API expansion — implementation and release gates

Base: 30f86d3. API reference: docs/Telegramads-API-INFORMATION.md and official https://ads.telegram.org/docs/api.

## Implemented in source (not runtime-certified)

| Commit | Scope |
|---|---|
| ba65d9d | Operator-mediated pause/resume, review, internal title, CPM/daily cap, audit and uncertainty lock |
| 6455253 | Signed budget increase/decrease proposals, no money movement |
| 8b78ec5 | Image/video validation, gated upload and content-bound media receipt |
| f39a1ff | Cursor-paginated ads list; staff account statistics, monthly report, ledger and transfer lookup |
| 71236e0 | Related account consent, request, gated operator provisioning and ownership binding |
| c6992c2 | Advanced channel/user criteria, exclusions, viewer timezone, website title/CTA |
| 590817c | Customer-scoped audience/pixel/event inventory and gated creation of empty groups and conversion resources |
| 73f2422 | Customer five-minute stats page, documented event types, escaped pixel snippet, regression tests |
| a0eb992 | Withdrawal of pending requests and malformed ID validation |
| (this batch) | Read-only reconciliation for uncertain remote edits; never retries or adjusts funds |

## Still required for complete delivery

- Execute full Django checks, migration consistency and pytest on a disposable DB with mocked API. Verify migrations forward/back, transaction locks and cross-tenant isolation. CI run 44527301151 finished failure with runner_id=0 and zero steps. No test result was obtained.
- Browser QA (mobile/desktop), RTL, real validation states, dialogs, accessibility and visual consistency. No screenshots or browser execution were available for this batch.
- Actual independent supplementary budget ledger, reservation/settlement and provider confirmation; decreasing a budget is not a fiat refund. Establish approved rules for exchange rate, fees, refunds, and withdrawal. Never mark a transfer successful on request alone.
- Related account campaign routing: every ad/stat/payment/import/operation/receipt must be scoped by immutable account identity; remote ad identifiers are not globally unique across accounts. Existing central-account records must be migrated and verified before routing or transferring funds to related accounts.
- Remaining remote edit/delete operations (creative, destination, schedule, deletion) and safe recovery/reconciliation of uncertain writes, with policy evaluation and verification of remote constraints.
- Audience contact import/add/remove/reset/delete and event rename/delete, website photo upload, conversion-event attachment to account-scoped campaigns; ensure lawful use of customer data and consent before contact transfers.
- Local rule-based notifications, automation proposals and assistant; do not turn on autonomous spending or claim ML functionality.
- Live API capability verification and documented operator/advertiser authorization; test only with explicitly authorized accounts and budget.

## Safety defaults

Keep TELEGRAM_ADS_WRITE_ENABLED and TELEGRAM_ADS_PAID_SUBMISSION_ENABLED false. New optional gates (MEDIA_UPLOAD, RELATED_ACCOUNTS, WEBSITE, CUSTOMER_ASSETS) also default false. Budget requests have no live execution adapter. Provisioning does not route campaigns or transfer credits. Existing central campaign routes cannot consume customer account assets. No Telegram live mutation, wallet debit, payment, or deployment was performed in this change set.

## Local verification

Use a disposable local database and test settings; do not run these commands against production.

```powershell
git pull --ff-only origin main
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest -q
```

Resolve any failures and perform UI QA before real deployment. Keep real API credentials out of logs and test fixtures.

- SHA-256-only audience add/remove management is implemented behind dedicated-account consent and customer asset write gates. It transmits explicit 64-digit hashes only; no phone numbers or hashes are retained in the database. Ambiguous writes remain unresolved and cannot be retried without reconciliation. Live verification required.

- Pre-payment creative photo/video uploads now persist an explicit uncertain claim before network I/O and use a standalone endpoint outside the wizard atomic block. Ambiguous upload outcomes cannot be automatically retried. Existing media-ownership and paid-submission gates remain unchanged.

- Safe audience deletion is gated by explicit ownership, confirmed ads_count == 0, durable idempotent claim and two-stage UX confirmation. Unknown ads_count blocks deletion. API writes remain disabled by default.
