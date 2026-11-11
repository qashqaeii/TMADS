# Production readiness checklist

## Security
- [ ] New `SECRET_KEY` and no default dev key
- [ ] `TELEGRAM_ADS_API_TOKEN` rotated (never use exposed tokens)
- [ ] `DEBUG=False`, HTTPS, secure cookies
- [ ] `TELEGRAM_ADS_WRITE_ENABLED` only when approved
- [ ] Real payment gateway configured; `PAYMENT_FAKE_ENABLED=False`

## Legal & compliance
- [ ] Telegram Ads account terms allow managed third-party campaigns
- [ ] `OperatorAdvertisingAuthorization` documented and `approved` before live writes
- [ ] `docs/TELEGRAM_ADS_POLICY_MAPPING.md` reviewed after Telegram guideline updates
- [ ] Terms, Privacy, Refund, Content policy content approved
- [ ] Customer policy center `/app/ad-policies/` reviewed (Persian summaries ≠ legal translation)
- [ ] Contact/billing identity configured

## Finance
- [ ] Active `ExchangeRate` with `irr_per_ton` in details
- [ ] Platform fee rules verified
- [ ] Wallet reconciliation process documented
- [ ] Idempotent payment callbacks tested

## Operations
- [ ] Staff roles assigned
- [ ] `detect_capabilities` run and reviewed
- [ ] Celery beat/worker running for stats sync
- [ ] Backup strategy for PostgreSQL

## QA
- [ ] `pytest` (including `tests/test_policies.py`) and `manage.py check` green
- [ ] Campaign pay flow blocks on policy `BLOCKED` findings
- [ ] Ops cannot approve campaigns with deterministic policy blocks
- [ ] Horizontal access tests pass
- [ ] Mobile smoke on dashboard and wizard
