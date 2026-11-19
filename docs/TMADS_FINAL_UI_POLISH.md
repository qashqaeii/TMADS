# TMADS Final visual polish — Executive Blue

Baseline: 9d1977ad6da1dd85f8d353ef54895a1e2b256339. Scope: presentation-only, Persian RTL, preserve all existing forms,
URLs, template context, authorization and financial gates. No production writes.
This pass uses one shared UI contract (ui-foundation.css), page-specific compositions
in separately named stylesheets and a shared accessible native confirmation dialog.
Do not add gradients/shadows to every control. Keep navy sidebar, clean white surfaces,
one blue primary action, semantic status colors, 9px controls, 12px surfaces, 42px
controls (44px mobile), keyboard focus and readable type. Use existing Lucide icons.
Keep legacy styles until their active usages can be safely migrated; no blanket purge.

## Completed source changes (commits)
- Foundation: e3bf6d9 — shared tokens, controls, feedback and native confirmation.
- Shell/dashboard/notifications: 407c683.
- Campaign list/detail/analytics: f7afac4.
- Studio/targeting/schedule/live approximate preview: 25e3907.
- Finance/wallet/top-up/ledger/invoice/refund: 4c5978b.
- Authentication/password recovery/profile: a1bcb9c.
- Support/policy center: 9d78db1.
- Operations review/rates/API/refunds/audit: 9e8e8cd.
- Public landing/features/how-it-works/pricing/FAQ/contact/legal: dbda9c3.
- Shared interaction and accessibility pass: d669b97.

Page-specific modules inherit the shared foundation and existing executive design.
Legacy CSS remains loaded for existing partial compatibility; removal requires
browser-based regression evidence. Do not claim measured UI quality or fully
verified production readiness from source edits. The landing illustration is
schematic, explicitly labeled as sample data. No financial or remote gates changed.

## Verification
Added template compile and customer/public route smoke tests plus a local-only
Playwright suite at three viewport sizes. These new tests have not been run in
the connector environment. Existing GitHub Actions executions failed before
runner allocation. Browser-level verification, Django test execution, staff
screens, all wizard branches, and populated financial/analytics states must be
checked against an isolated running environment before deployment.
