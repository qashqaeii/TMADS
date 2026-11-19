# Public editorial SEO and UI
- Content is server-rendered in Persian and organized around search intent: home (Telegram Ads introduction), features (capabilities), how-it-works (process), pricing (budget and cost), FAQ (questions), about (trust), contact (support).
- Unique metadata, canonical, robots and sitemap are retained. WebSite and BreadcrumbList JSON-LD are limited to canonical public routes; no fabricated review, rating, price or FAQ rich-result markup.
- Auth pages and legal drafts remain noindex. Legal texts still require review.
- Public CSS: responsive editorial grid, focus indicators, reduced motion, restrained typography, touch targets, auth guidance.
- Sources: https://developers.google.com/search/docs/fundamentals/seo-starter-guide ; https://developers.google.com/search/docs/appearance/structured-data/breadcrumb ; https://ads.telegram.org/guidelines ; https://ads.telegram.org/getting-started/.
- Before release: configure PUBLIC_SITE_URL with the real HTTPS origin; verify indexing and sitemap in Search Console; audit real pages for Core Web Vitals, keyboard navigation, responsive layout and actual accessibility. No search ranking or browser compliance is claimed from code alone.
