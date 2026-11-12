# TMADS — unified premium redesign

User removed the deadline. Continue until every template meets the agreed design and verification criteria.
Baseline: e12297395a486f40475e4a96e592341b88f4ced9. Scope: all 71 HTML templates, including shared partials, public, auth, customer and operations pages.

## Design contract

Implement a restrained, coherent Persian RTL premium SaaS design, preserving Telegram blue brand identity. This is an implementation assignment, not an audit-only task. Use a single documented token/component system; no repeated aesthetic rewrites.

- Surfaces: canvas #F6F8FB, white cards, text #142437, muted #5D6B7C, borders #E4EAF1. Brand #2AABEE; darker action blue #087DB7 for white-text controls, verify contrast. Semantic success/warning/error muted and readable.
- Typography: consistent Persian-capable font stack; use available approved font resources, readable body 14–16px, clear compact headings, tabular numeric amounts. Preserve Persian/Latin direction where appropriate.
- Spacing: 4/8/12/16/24/32/48px scale. Card radius 16px, controls 10px, subtle borders/shadows. Avoid heavy boxes, excessive gradients and decorative clutter.
- Shared components: shell/sidebar/mobile navigation, header, button, form field, select/checkbox, tabs, KPI, table/mobile record, badge, modal, toast, empty/loading/error state and chart frame.
- One clear primary action per section; useful data density; consistent mobile touch targets near 44px; visible keyboard focus, labels, semantic headings, reduced motion. No horizontal page overflow at 390/768/1440px; data tables may have deliberate contained scrolling.
- Preserve existing routes, Django blocks/context, CSRF, permission guards, input names, JS hooks, event bindings, financial numbers and actual functionality.

Explicit detail scope: sidebars, headers, KPI cards, tables, dialogs/modals, dropdown menus, subtle enter/exit transitions, hover/focus/pressed/disabled states. Motion must be restrained, interruptible, and respect reduced-motion preferences. Preserve focus and keyboard usability.

## Execution order

1. Foundations: inspect existing CSS cascade; implement tokens and shared components coherently, avoiding an additional giant layer of overrides. Update base, app/public shells and shared includes. Document component usage.
2. Customer dashboard, campaign list/detail and all five studio steps and partials.
3. Wallet, top-up, transactions, invoices, refunds; all seven operations templates.
4. Support, notifications, profile, auth/password reset; public home and all informational/legal pages.
5. Coverage audit, mobile/desktop verification, template rendering and existing test suite; fix concrete regressions, finish report.

Each execution must implement as much of the remaining work as feasible, not stop after one tiny edit. Re-read latest remote head and this inventory. Commit coherent completed batches to main, preserve concurrent work, never force-push. Record exact verification and remaining tasks. Shared component inheritance counts only after inspecting the consuming template; do not check all pages merely because a stylesheet changed.

Scope is UI/UX: do not change payment, ledger, permissions, Telegram Ads integration, backend business logic, migrations or production data. Do not deploy or execute real payments/ad submissions. Keep live-write gates disabled. Local isolated fixtures may be used for visual checking. Preserve unrelated changes. Browser visual QA is explicitly part of this user-requested complete redesign and verification; older audit docs' lack of permission does not limit this request.

For repeatability use the GitHub source and this document; do not rely on transient filesystem state. If execution tools, dependencies or preview are unavailable, complete safe source changes and report the verification gap accurately. Never claim executed tests/screenshots without evidence.

## Completion criteria

Every inventory row has implementation status and verification evidence; consistent tokens/components across all page families; responsive RTL flows preserve behavior; actual checks recorded, no false pass claims. Report completed/remaining/blocked work and commit URLs after each run. Once complete, pause the automation; no endless polishing.

## Inventory

| Template | Implementation | Verification |
|---|---|---|
| `templates/accounts/login.html` | Pending | Not verified in this pass |
| `templates/accounts/password_reset.html` | Pending | Not verified in this pass |
| `templates/accounts/password_reset_complete.html` | Pending | Not verified in this pass |
| `templates/accounts/password_reset_confirm.html` | Pending | Not verified in this pass |
| `templates/accounts/password_reset_done.html` | Pending | Not verified in this pass |
| `templates/accounts/profile.html` | Pending | Not verified in this pass |
| `templates/accounts/register.html` | Pending | Not verified in this pass |
| `templates/app_shell.html` | Pending | Not verified in this pass |
| `templates/base.html` | Pending | Not verified in this pass |
| `templates/campaigns/detail.html` | Pending | Not verified in this pass |
| `templates/campaigns/includes/list_page_header.html` | Pending | Not verified in this pass |
| `templates/campaigns/includes/list_row_actions.html` | Pending | Not verified in this pass |
| `templates/campaigns/includes/policy_panel.html` | Pending | Not verified in this pass |
| `templates/campaigns/includes/schedule_grid.html` | Pending | Not verified in this pass |
| `templates/campaigns/includes/studio_preview.html` | Pending | Not verified in this pass |
| `templates/campaigns/includes/targeting_board.html` | Pending | Not verified in this pass |
| `templates/campaigns/list.html` | Pending | Not verified in this pass |
| `templates/campaigns/wizard.html` | Pending | Not verified in this pass |
| `templates/dashboard/home.html` | Pending | Not verified in this pass |
| `templates/dashboard/notifications.html` | Pending | Not verified in this pass |
| `templates/finance/invoice_detail.html` | Pending | Not verified in this pass |
| `templates/finance/invoices.html` | Pending | Not verified in this pass |
| `templates/finance/refunds.html` | Pending | Not verified in this pass |
| `templates/finance/topup.html` | Pending | Not verified in this pass |
| `templates/finance/transactions.html` | Pending | Not verified in this pass |
| `templates/finance/wallet.html` | Pending | Not verified in this pass |
| `templates/includes/app_page_header.html` | Pending | Not verified in this pass |
| `templates/includes/brand_mark.html` | Pending | Not verified in this pass |
| `templates/includes/campaign_actions_menu.html` | Pending | Not verified in this pass |
| `templates/includes/campaign_budget_band.html` | Pending | Not verified in this pass |
| `templates/includes/campaign_delete_form.html` | Pending | Not verified in this pass |
| `templates/includes/campaign_lifecycle.html` | Pending | Not verified in this pass |
| `templates/includes/campaign_metrics_strip.html` | Pending | Not verified in this pass |
| `templates/includes/chart_empty_dash.html` | Pending | Not verified in this pass |
| `templates/includes/chart_range.html` | Pending | Not verified in this pass |
| `templates/includes/charts_exec_scripts.html` | Pending | Not verified in this pass |
| `templates/includes/dash_header.html` | Pending | Not verified in this pass |
| `templates/includes/dash_home_hero.html` | Pending | Not verified in this pass |
| `templates/includes/dash_home_kpi.html` | Pending | Not verified in this pass |
| `templates/includes/dashboard_performance_strip.html` | Pending | Not verified in this pass |
| `templates/includes/kpi_exec_card.html` | Pending | Not verified in this pass |
| `templates/includes/kpi_icon.html` | Pending | Not verified in this pass |
| `templates/includes/kpi_luxe.html` | Pending | Not verified in this pass |
| `templates/includes/lucide_icon.html` | Pending | Not verified in this pass |
| `templates/includes/metric_strip.html` | Pending | Not verified in this pass |
| `templates/includes/nav_icon.html` | Pending | Not verified in this pass |
| `templates/includes/portfolio_metric_strip.html` | Pending | Not verified in this pass |
| `templates/includes/public_hero.html` | Pending | Not verified in this pass |
| `templates/includes/rate_strip.html` | Pending | Not verified in this pass |
| `templates/includes/ton_amount.html` | Pending | Not verified in this pass |
| `templates/includes/wallet_module_compact.html` | Pending | Not verified in this pass |
| `templates/operations/api_status.html` | Pending | Not verified in this pass |
| `templates/operations/audit_logs.html` | Pending | Not verified in this pass |
| `templates/operations/campaign_review.html` | Pending | Not verified in this pass |
| `templates/operations/campaigns.html` | Pending | Not verified in this pass |
| `templates/operations/exchange_rates.html` | Pending | Not verified in this pass |
| `templates/operations/overview.html` | Pending | Not verified in this pass |
| `templates/operations/refunds.html` | Pending | Not verified in this pass |
| `templates/policies/ad_policies.html` | Pending | Not verified in this pass |
| `templates/public/about.html` | Pending | Not verified in this pass |
| `templates/public/contact.html` | Pending | Not verified in this pass |
| `templates/public/faq.html` | Pending | Not verified in this pass |
| `templates/public/features.html` | Pending | Not verified in this pass |
| `templates/public/home.html` | Pending | Not verified in this pass |
| `templates/public/how_it_works.html` | Pending | Not verified in this pass |
| `templates/public/legal_page.html` | Pending | Not verified in this pass |
| `templates/public/pricing.html` | Pending | Not verified in this pass |
| `templates/public_base.html` | Pending | Not verified in this pass |
| `templates/support/create.html` | Pending | Not verified in this pass |
| `templates/support/detail.html` | Pending | Not verified in this pass |
| `templates/support/list.html` | Pending | Not verified in this pass |

## Progress

- Planning: full HTML inventory captured from remote main; design contract and bounded execution workflow recorded.
- Foundation implementation started: commit e949e66496685604f8eac2b20e3d1fb95eb07c5e updates existing color/motion tokens and restores explicit topbar keyboard focus. No template is marked complete yet.
- Verification: static inspection of 9 intended replacements; CSS brace balance zero; calculated white/action contrast 4.88:1 and white/muted text contrast 5.44:1 for the updated solid tokens. These measurements do not certify all component combinations. No runtime/browser tests executed in this pass. Earlier reports are historical only.

- Automation configured hourly at :30 Asia/Tehran with no deadline; stop after completion. Routine progress belongs in this document, not user notifications. Ask only for a genuine blocker requiring user intervention. Next: complete shared components/cascade review and inspect all consuming templates, then proceed through the inventory.
