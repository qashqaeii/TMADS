# GramAds Workspace — reference design
The reference page is /app/. Adopt .ga-workspace-system and gramads-workspace-system.css on future pages deliberately; do not apply styles globally.

- Density: 12px section rhythm, 15px card radius, 9px controls, 100px desktop KPI cards. Header stays compact. One primary action and one blue KPI surface; white/light surfaces for the rest.
- Typography: hierarchy via weight and scale, tabular numbers, Persian digits, explicit labels. Never create fake deltas or placeholder financial values.
- Icons: local outline SVG via includes/gramads_workspace_icon.html, 18/21px, decorative, currentColor; use explicit text labels for actions. No new external image dependency.
- Motion: 160–260ms easing, short entrance stagger, at most 2px card lift. Keyboard focus, reduced motion and touch layouts are required. Avoid animations that conceal data or shift layout.
- Cards and data: consistent borders, restrained shadows, tinted status with text. Recent campaign rows use the same grid as their column headings. On narrow content widths, read as stacked compact cards with visible metric labels.
- Charts: show full server-supplied range, no artificial points, muted bars and distinct line, reduced motion. Preserve actual data and empty values.
- Validation: run Django tests and authenticated Playwright at 375/768/1440px. Check narrow-screen overflow, keyboard focus, real chart data and empty/populated wallets. Existing quality CI checks Django and JS, not browser E2E.
