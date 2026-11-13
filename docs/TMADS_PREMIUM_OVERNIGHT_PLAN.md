# TMADS — unified premium redesign

User removed the deadline. Continue until every template meets the agreed design and verification criteria.
Baseline: e12297395a486f40475e4a96e592341b88f4ced9. Scope: original 71 HTML templates plus the shared auth_field.html (72 total), including shared partials, public, auth, customer and operations pages.

## Design contract

Implement a restrained, coherent Persian RTL premium SaaS design, preserving Telegram blue brand identity. This is an implementation assignment, not an audit-only task. Use a single documented token/component system; no repeated aesthetic rewrites.

- Surfaces: canvas #F6F8FB, white cards, text #142437, muted #5D6B7C, borders #E4EAF1. Brand #2AABEE; darker action blue #0878AD for white-text controls, verify contrast. Semantic success/warning/error muted and readable.
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
| `templates/accounts/login.html` | Implemented; visual QA pending | Django compile/render checked; browser unavailable |
| `templates/accounts/password_reset.html` | Implemented; visual QA pending | Django compile/render checked; browser unavailable |
| `templates/accounts/password_reset_complete.html` | Implemented; visual QA pending | Django compile/render checked; browser unavailable |
| `templates/accounts/password_reset_confirm.html` | Implemented; visual QA pending | Django compile/render checked; browser unavailable |
| `templates/accounts/password_reset_done.html` | Implemented; visual QA pending | Django compile/render checked; browser unavailable |
| `templates/accounts/profile.html` | Implemented; visual QA pending | Compiled and empty/populated GETs verified |
| `templates/accounts/register.html` | Implemented; visual QA pending | Django compile/render checked; browser unavailable |
| `templates/app_shell.html` | Implemented; visual QA pending | Django compile/render checked; browser unavailable |
| `templates/base.html` | Implemented; visual QA pending | Django compile/render checked; browser unavailable |
| `templates/campaigns/detail.html` | In progress; shared interaction/readability pass | Django compilation and existing suite passed; visual QA pending |
| `templates/campaigns/includes/list_page_header.html` | In progress; shared interaction/readability pass | Django compilation and existing suite passed; visual QA pending |
| `templates/campaigns/includes/list_row_actions.html` | In progress; shared interaction/readability pass | Django compilation and existing suite passed; visual QA pending |
| `templates/campaigns/includes/policy_panel.html` | Implemented; visual QA pending | Compiled; studio GET matrix and existing tests passed |
| `templates/campaigns/includes/schedule_grid.html` | Implemented; visual QA pending | Compiled; studio GET matrix and existing tests passed |
| `templates/campaigns/includes/studio_preview.html` | Implemented; visual QA pending | Compiled; studio GET matrix and existing tests passed |
| `templates/campaigns/includes/targeting_board.html` | Pending | Not verified in this pass |
| `templates/campaigns/list.html` | In progress; shared interaction/readability pass | Django compilation and existing suite passed; visual QA pending |
| `templates/campaigns/wizard.html` | Implemented; visual QA pending | Compiled; studio GET matrix and existing tests passed |
| `templates/dashboard/home.html` | In progress; shared interaction/readability pass | Django compilation and existing suite passed; visual QA pending |
| `templates/dashboard/notifications.html` | Implemented; visual QA pending | Compiled and empty/populated GETs verified |
| `templates/finance/invoice_detail.html` | Implemented; visual QA pending | Compiled; authenticated financial GET checks and existing suite passed |
| `templates/finance/invoices.html` | Implemented; visual QA pending | Compiled; authenticated financial GET checks and existing suite passed |
| `templates/finance/refunds.html` | Implemented; visual QA pending | Compiled; authenticated financial GET checks and existing suite passed |
| `templates/finance/topup.html` | Implemented; visual QA pending | Compiled; authenticated financial GET checks and existing suite passed |
| `templates/finance/transactions.html` | Implemented; visual QA pending | Compiled; authenticated financial GET checks and existing suite passed |
| `templates/finance/wallet.html` | Implemented; visual QA pending | Compiled; authenticated financial GET checks and existing suite passed |
| `templates/includes/app_page_header.html` | Pending | Not verified in this pass |
| `templates/includes/brand_mark.html` | Pending | Not verified in this pass |
| `templates/includes/campaign_actions_menu.html` | In progress; shared interaction/readability pass | Django compilation and existing suite passed; visual QA pending |
| `templates/includes/campaign_budget_band.html` | Pending | Not verified in this pass |
| `templates/includes/campaign_delete_form.html` | Pending | Not verified in this pass |
| `templates/includes/campaign_lifecycle.html` | Pending | Not verified in this pass |
| `templates/includes/campaign_metrics_strip.html` | Pending | Not verified in this pass |
| `templates/includes/chart_empty_dash.html` | Pending | Not verified in this pass |
| `templates/includes/chart_range.html` | In progress; shared interaction/readability pass | Django compilation and existing suite passed; visual QA pending |
| `templates/includes/charts_exec_scripts.html` | Pending | Not verified in this pass |
| `templates/includes/dash_header.html` | In progress; shared interaction/readability pass | Django compilation and existing suite passed; visual QA pending |
| `templates/includes/dash_home_hero.html` | In progress; shared interaction/readability pass | Django compilation and existing suite passed; visual QA pending |
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
| `templates/public_base.html` | Implemented; visual QA pending | Django compile/render checked; browser unavailable |
| `templates/support/create.html` | Implemented; visual QA pending | Compiled and empty/populated GETs verified |
| `templates/support/detail.html` | Implemented; visual QA pending | Compiled and empty/populated GETs verified |
| `templates/support/list.html` | Implemented; visual QA pending | Compiled and empty/populated GETs verified |

| `templates/includes/auth_field.html` | Implemented; visual QA pending | Shared bound field/error/help rendering checked |

## Progress

- Planning: full HTML inventory captured from remote main; design contract and bounded execution workflow recorded.
- Foundation implementation started: commit e949e66496685604f8eac2b20e3d1fb95eb07c5e updates existing color/motion tokens and restores explicit topbar keyboard focus. No template is marked complete yet.
- Verification: static inspection of 9 intended replacements; CSS brace balance zero; calculated white/action contrast 4.88:1 and white/muted text contrast 5.44:1 for the updated solid tokens. These measurements do not certify all component combinations. No runtime/browser tests executed in this pass. Earlier reports are historical only.

- Automation configured hourly at :30 Asia/Tehran with no deadline; stop after completion. Routine progress belongs in this document, not user notifications. Ask only for a genuine blocker requiring user intervention. Next: complete shared components/cascade review and inspect all consuming templates, then proceed through the inventory.

## Batch 1 — navigation, shared controls and authentication

- Updated existing component rules in design-executive.css (not a new override stylesheet): spacing/control tokens, 44px touch controls, focus indication, invalid/disabled field states, auth spacing and sidebar label contrast.
- Base/app/public shells: skip navigation, mobile drawer close control, correct RTL drawer edge, initial backdrop cloaking, focus containment/restoration and inert background, current-page indication. Preserved Alpine open/close handlers and all routes. Account links now use ordinary link semantics instead of incomplete ARIA menu roles.
- Six authentication templates: shared bound fields with labels/help/errors, login autocomplete, recovery success icon/state and consistent actions. Removed environment label from public footer.
- Verification during preparation: manage.py check clean; collectstatic completed; all 72 templates compiled; invalid registration, dashboard shell and both reset-confirm branches rendered. Existing suite: 70 passed in 14.43s after installing environment-only socksio and collecting static assets (NOBITEX_HTTP_TIMEOUT_SECONDS=1, NOBITEX_HTTP_RETRIES=0). node --check navigation.js passed. No backend or requirements files changed.
- Browser attempt failed: installed Chromium launch rejected socket() with Operation not permitted; bundled browser download also returned a truncated archive. No visual viewport pass is claimed. Browser QA at 390/768/1440 remains pending; this does not block remaining source work.
- Next: support/profile/notifications, then campaign/customer shared components. Preserve this batch rather than repeating it. Implementation commit: [fd9c31a](https://github.com/qashqaeii/TMADS/commit/fd9c31a603b9a2b0a511660b38cfe5da070d2ba4).

## Batch 2 — profile, support and notifications

- Profile uses labelled fields, isolated LTR contact values, shared password error/help components and aligned form spacing.
- Ticket form now has explicit field labels, clear back/submit actions; conversation preserves line breaks, distinguishes support replies, wraps long text and provides labelled reply composer and timestamps.
- Ticket list uses semantic timestamps; notifications have a non-color unread indicator for assistive technology, readable empty state and hide the unnecessary bulk action when empty.
- Existing CSS component rules extended in place; no backend files, routes, permissions, form names or financial logic changed.
- Current verification: manage.py check clean; all 72 templates compile; seven authenticated GETs cover profile and support/notifications empty and populated states using transaction-rolled-back local fixtures. CSS parse: zero errors. Existing pytest suite: 70 passed in 21.66s with environment-only socksio plus 1s/no-retry Nobitex test configuration. Navigation JS syntax checked. Browser interaction/viewport QA remains pending due to launch restriction recorded above.
- Next execution: dashboard and campaign shared headers/KPI/menus, then wizard. Do not treat pending visual QA as completed. Review the inherited components in each consumer before updating its inventory row.

## Batch 3 — dashboard readability and campaign interactions

Implementation commit: [db1decd](https://github.com/qashqaeii/TMADS/commit/db1decd0c6d3418366ccfb308457e7ad0d8a069a).

- Previous batch implementation: [61be12c](https://github.com/qashqaeii/TMADS/commit/61be12c4d4a34b52cb73980caef776b6d9f22c57).
- Dashboard header/hero: visible contextual subtitle, explicit toman label and readable stale-rate text; increased KPI label size in the existing component rule. Dashboard record timestamps now expose machine-readable dates.
- Campaign list: scoped table headings, caption and keyboard-focusable scroll region; concise header description and labelled row disclosure. Detail action menu now uses native details/summary; existing URLs, delete guard, confirmation and CSRF remain intact.
- Shared interactions: Escape restores disclosure focus, outside clicks dismiss disclosures, opening one closes others. Campaign tabs support RTL arrow keys and Home/End via existing click handlers; panels are keyboard focusable. Chart range buttons expose initial pressed state. Menu controls use consistent touch sizes, restrained entrance motion and reduced-motion opt-out.
- Files: templates/dashboard/home.html; templates/campaigns/{list,detail}.html; templates/campaigns/includes/{list_page_header,list_row_actions}.html; templates/includes/{dash_header,dash_home_hero,campaign_actions_menu,chart_range}.html; static/js/navigation.js; static/css/design-executive.css.
- Verification actually executed: 70 existing pytest tests passed in 18.46s (NOBITEX_HTTP_TIMEOUT_SECONDS=1, NOBITEX_HTTP_RETRIES=0); manage.py check clean; collectstatic completed; all 72 templates compiled with config.settings.local; CSS top-level parse zero errors; node --check navigation.js passed. An initial compilation command used the settings package instead of local settings and failed to locate templates; corrected command passed.
- Browser interaction and 390/768/1440 visual QA remain pending; no screenshots or visual completion claimed. Source changes are a coherent improvement pass, not certification of the full dashboard/campaign family. No backend changes.
- Next: complete wizard and its targeting/schedule/preview/policy partials; then finance/operations/public families. Leave automation active.

## Batch 4 — five-step studio, preview and weekly schedule

Implementation commit: [85487e8](https://github.com/qashqaeii/TMADS/commit/85487e8845f9e0c0330c03a2280b8a72fac2d42c).

- Studio: associated 24 previously unbound field labels with controls, marked current progress step, clarified professional-mode copy, unified form/preview surfaces and spacing, added visible focus to choice cards and responsive action buttons. Existing POST names, target choices, financial fields and submit actions are preserved.
- Preview partial: named complementary region and semantic heading, shared search icon, long-content wrapping. Policy panel: Persian severity labels while retaining existing severity classes, findings, guards and refresh hooks.
- Weekly schedule: 44px hour targets with contained horizontal scrolling and sticky day labels. Added named cells and roving keyboard focus (RTL left/right, up/down, Home/End); Space/Enter use the existing toggle handler. No schedule mask, timezone or persistence logic changed.
- Files: templates/campaigns/wizard.html; templates/campaigns/includes/{schedule_grid,studio_preview,policy_panel}.html; static/css/design-executive.css; static/js/ad-studio.js.
- Verification: manage.py check clean; collectstatic completed; node --check ad-studio.js passed; all 72 templates compiled; CSS parsed without top-level errors. Existing suite: 70 passed in 17.32s. Additional isolated, transaction-rolled-back GET matrix: 20 passed in 5.28s (four targeting types × five wizard steps; status, current-step markup, preview heading and CSRF checks). Test-only temporary matrix was not committed. Same environment-only 1s/no-retry Nobitex configuration as previous batch.
- Browser QA at 390/768/1440 remains pending under the previously recorded browser restriction. Keyboard code was syntax checked, not browser-interaction certified. No visual completion claim; automation remains active.
- Next: finance and operations page families; retain this implementation and complete cross-page visual QA when a browser is available. Targeting board and other shared includes still need the inventory review.

## Batch 5 — customer finance pages

- Wallet: explicit toman units and semantic transaction timestamps, clear transaction link; mobile summary uses two columns. Top-up and refund forms: bound labels, readable spacing, amount help, back navigation and an explanation when no eligible order exists. POST names, minimum amount, eligibility/disabled guards and CSRF unchanged.
- Transactions/invoices/refunds: named keyboard-focusable scroll regions, table captions, scoped headers and semantic dates; clearer empty transaction state and explicit balance units.
- Invoice detail: a named summary surface with long description/reference wrapping. Added a compact finance component section beside existing wallet rules, using shared spacing/color/radius tokens; no new animation or override stylesheet.
- Files: templates/finance/{wallet,topup,transactions,invoices,invoice_detail,refunds}.html; static/css/design-executive.css.
- Actual validation: environment dependencies had to be reinstalled after Django was initially unavailable (no requirements changes). manage.py check clean; collectstatic completed; CSS parsed without top-level errors. Existing suite: 70 passed in 18.71s. Temporary isolated finance check: 1 passed in 1.62s, covering seven authenticated GETs (five list/form routes plus populated invoice list/detail) and compilation of all 72 templates. Used 1s/no-retry Nobitex environment settings. Temporary check not committed.
- No live payments, deployment or production data changes. Browser screenshots/interaction and 390/768/1440 viewport checks remain unverified under the previously recorded environment limitation. All source work is retained; do not count visual QA as completed.
- Next: seven operations templates, public page family, remaining shared includes; then cross-page QA and completion review. Automation remains active.
