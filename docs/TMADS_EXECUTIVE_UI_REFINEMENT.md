# Executive UI refinement — final source pass

Baseline 848050a; no payment, Telegram mutation, credentials or deployment performed.
Preserve the existing design system rather than replacing active legacy partials.
The shared tokens, control states, dialogs, responsive tables and layout are used across public and private pages.

## Commits in this UI pass
- 65ac9b5: foundation, navigation and controls.
- 37ff358: public editorial pages, schematic product visual, authentication surfaces.
- d814a5c: dashboard composition, notifications, campaign list and detail, studio layout.
- 34d77f2: finance, support, reports, customer resources, account inventory template and operations.
- Final batch: release-readiness presentation and regression coverage.

Concurrent changes from other workstreams are preserved; this pass changes presentation and UI coverage, not those service contracts.

## Acceptance
Load public, customer, staff, and new API-resource routes in an isolated local environment.
Check 390, 768, 1280, 1440px, with real populated, empty, error and blocked states.
Verify no page-level horizontal overflow, visible focus, native confirm dialog cancellation, RTL reading order, readable tables, and every wizard step.
No real payment, ad submission, account creation, contact upload, or deletion for UI tests.
The browser suite and Django compile/smoke tests are added or extended; actual runner results must be reported separately. A failed job without an allocated runner is not evidence of test execution.
