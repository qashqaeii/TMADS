# GramAds Workspace — reference design
The reference page is /app/. Adopt .ga-workspace-system and gramads-workspace-system.css on future pages deliberately; do not apply styles globally.

- Density: 12px section rhythm, 15px card radius, 9px controls, 100px desktop KPI cards. Header stays compact. One primary action and one blue KPI surface; white/light surfaces for the rest.
- Typography: hierarchy via weight and scale, tabular numbers, Persian digits, explicit labels. Never create fake deltas or placeholder financial values.
- Icons: local outline SVG via includes/gramads_workspace_icon.html, 18/21px, decorative, currentColor; use explicit text labels for actions. No new external image dependency.
- Motion: 160–260ms easing, short entrance stagger, at most 2px card lift. Keyboard focus, reduced motion and touch layouts are required. Avoid animations that conceal data or shift layout.
- Cards and data: consistent borders, restrained shadows, tinted status with text. Recent campaign rows use the same grid as their column headings. On narrow content widths, read as stacked compact cards with visible metric labels.
- Charts: show full server-supplied range, no artificial points, muted bars and distinct line, reduced motion. Preserve actual data and empty values.
- Validation: run Django tests and authenticated Playwright at 375/768/1440px. Check narrow-screen overflow, keyboard focus, real chart data and empty/populated wallets. Existing quality CI checks Django and JS, not browser E2E.

## Rollout
The app shell opts into the token system. `gramads-workspace-pages.css` is loaded after the legacy modules, scoped to `body.is-app`; home composition remains isolated. Major module blocks cover campaigns (including studio and detail), advertiser account and profile, finance including payment pages, support/policies/notifications, and operator console. Native confirmation, disclosure menus and notices retain their existing action handlers and keyboard semantics.
 
- Avoid new inline styles for shared components. Keep public styles separate, use the local named outline icons for page headers and retain existing icons where needed.
- Financing and authorization remain server-controlled. Do not replace missing data with zero or invent metrics.
- Regression tests cover rendered customer pages, responsive customer/operator route sweeps and confirmation cancellation. Run browser tests against a disposable instance with provider writes and paid submissions disabled. Inspect all populated and empty states; successful CI is not a visual sign-off.
