# TMADS — hardening and product completion

## Execution contract

User authorized successive focused commits to main and requested autonomous completion
in priority order, including premium Persian RTL UX. The baseline was
e7c3f4f6374eae564b44f7232eabf6202b2010d8. Read the latest main and this document
before every batch. Preserve concurrent work; use fast-forward updates only.
Keep changes scoped and do not repeatedly redesign already completed pages.
Never deploy, use production data or credentials, spend funds, enable real
payment/submission or Telegram write flags, or fabricate operator authorization.
Automated verification must use isolated test data and mocked external writes.

## Implemented in source (runtime verification pending)

| Commit | Scope |
|---|---|
| 16cc78c | Audience-step validation and review integrity; regression tests |
| 3c35465 | Locked price quote, stale quote protection, checkout and edit guard, quote UX |
| e2a3906 | Payment transaction integrity, authority check, order-scoped reservation/refund |
| 8e0da63 | Telegram budget precision, locked TON/daily amount and stable create key |
| 12d0c89 | Paid submission guard, claim, duplicate prevention, uncertain outcome reconciliation state |
| 0e9ef3f | Server-verified bot eligibility, safe DOM rendering and selector UX |
| 053348d | Paid order operations review and recorded approval, remove arbitrary remote linking |
| 0035e53 | GitHub Actions checks, migrations, static assets, JS syntax and pytest |
| 574d6bf | Serialized autosave, revision checks, non-persistent policy preview and local template selection |
| 0f12e05 | Budget/CPM/date validation, step-owned settings, regression tests |
| d4cf6de | Fail-closed production settings, default storage configuration and local-only Docker ports/build context |

All commits were created and main was advanced without force. None of the new
regression tests have been independently executed successfully yet. Prior historical
test counts do not prove the current version.

## Verification blocker (P0)

GitHub Actions workflow exists, but runs 44498451742, 44498993074, 44499383325,
44499744460 concluded failure with no executed steps reported. Latest job
135476061311 had an empty steps array. Initial logs were unavailable (404) and
annotations were not accessible through the connector. Do not infer a billing
or code failure. Inspect actual run status/annotations and obtain an isolated
checkout/test environment if available. Never weaken tests to pass. Add
PostgreSQL concurrency coverage and real E2E browser tests; report exact output.
If only the repository connector is available, mark source changes unverified.

## Remaining priorities

- [ ] P0: Establish working CI or isolated runtime; run Django checks,
  migration drift, pytest and JS syntax; correct any real regressions. Recheck
  changes above against full current sources, including compatibility with
  existing tests, stale forms, older orders and operator approvals.
- [ ] P0: Finish financial reconciliation/settlement. On confirmed Telegram
  debit/allocation evidence, distinguish purchased remote credit from actual ad
  spend; settle the correct order idempotently using a documented ledger model.
  Never release customer funds merely on timeout; no arbitrary remote ID
  attachment or resubmission. Explicitly account for service fee and risk
  buffer under approved commercial terms; legacy records require safe
  reconciliation. Do not auto-refund allocated remote credit without proof
  of return and permitted policy. Test races and duplicate receipts.
- [ ] P0: Finish payment provider reference uniqueness, duplicate callback
  handling, refund review/reject races, unit conversion contract, real gateway
  configuration and failure states, all without real transactions.
- [ ] P1: Media: validate actual image contents via Pillow and real MP4
  container/codec checks, provide actionable Persian field errors and removal,
  prevent cross-customer downloads. Verify the installed telead wrapper and
  official upload API before implementing gated photo/video upload. Until
  supported, do not silently omit media from a paid advert.
- [ ] P1: Targeting: eliminate synthetic selectable fallback IDs, verify
  channel/topic/location mapping and unknown API states, optimize lookup queue,
  test four ad types end-to-end and eligibility refresh; keep source truth.
- [ ] P1: Analytics: audit period/lifetime definitions, action labels, currency,
  spend and freshness; no fabricated values. Check pagination/filter query
  encoding, mobile UI, accessible feedback, empty/error states.
- [ ] P1: Complete UI/UX checklist from TMADS_PREMIUM_OVERNIGHT_PLAN.md, focused
  on real form states, sidebar, dashboard, financial flows, ops and responsive
  Persian RTL. Preserve WebP assets and current brand; don't add redundant
  rewrite passes. Screenshot and interaction QA at mobile/tablet/desktop when
  an actual browser is available.
- [ ] P2: Deployment guide, migration/backups, secrets, private media storage,
  production worker/cache configuration and observability; document launch
  requirements. External gates: actual operator authorization, real
  Telegram/account/payment access and actual deploy approval remain separate.

## Completion criterion

All feasible software tasks implemented and committed, regression tests green
in an isolated runtime with evidence, actual visual checks recorded, and
external launch blockers clearly separated. Record completed work, commit SHA,
verification and remaining tasks here after each coherent batch. Stop only
when completed or when a genuine blocker prevents safe further progress.

## Next batch — verified allocation settlement
Source implementation: unique create receipt and strict read-only transaction evidence;
locked allocation and service fee consume the order reservation separately from actual
ad views spend. New quotes explicitly return the temporary rate buffer after verified
allocation. Old quotes without these terms, incomplete histories, or missing create
receipts remain locked for manual reconciliation. Remote sync no longer overwrites
pending submission/reconciliation. Runtime and browser verification remain pending.

## Payment provider and refund integrity
Request and verify now use the same explicitly declared IRR amount; see third-party
v4 implementations https://github.com/common-repository/zarinpal-woocommerce-payment-gateway/blob/main/class-wc-gateway-zarinpal.php
and https://github.com/jnjal/zarinpal-js. Official/live provider verification remains
required prior to production; no real request was made. Legacy pending requests without
stored provider amount are blocked for manual verification, not reinterpreted. A conditional
unique constraint rejects reuse of gateway authority; migration fails safely if legacy duplicates
exist. Refund review and rejection now follow the same lock order as approval; filter before slice.
