# TMADS Final visual polish — Executive Blue

Baseline: 9d1977ad6da1dd85f8d353ef54895a1e2b256339. Scope: presentation-only, Persian RTL, preserve all existing forms,
URLs, template context, authorization and financial gates. No production writes.
This pass uses one shared UI contract (ui-foundation.css), page-specific compositions
in separately named stylesheets and a shared accessible native confirmation dialog.
Do not add gradients/shadows to every control. Keep navy sidebar, clean white surfaces,
one blue primary action, semantic status colors, 9px controls, 12px surfaces, 42px
controls (44px mobile), keyboard focus and readable type. Use existing Lucide icons.
Keep legacy styles until their active usages can be safely migrated; no blanket purge.

## Work ledger
- Shared foundation: control variants, fields, status, feedback, overlay, delete confirmation.
- Remaining: shell/mobile, dashboard, campaign list/detail, studio, finance, account/support,
  operations, public pages, inventory of partials and verification.
- Current verification: source only. Previous GitHub Actions had no runner or steps;
  browser and runtime QA must be reported separately, never claimed from static inspection.
