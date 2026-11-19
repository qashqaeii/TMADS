# Public content and search optimization

## Five implementation phases

1. Technical SEO: unique titles and descriptions, canonical HTTPS origin, Open Graph, robots.txt and XML sitemap.
2. Landing: definition of Telegram Ads, use cases, value proposition, internal links, decision FAQs and conversion.
3. Product: features, step-by-step guide and pricing, including a clearly illustrative CPM calculation.
4. Trust: about, support, 16 FAQs, legal navigation. Existing legal draft text is retained until reviewed.
5. Conversion and verification: login, register, password reset, regression tests and deployment configuration.

## Search intent map (hypotheses, not measured volumes)

| Page | Primary intent |
| --- | --- |
| / | تبلیغات تلگرام / تلگرام ادز |
| /features/ | پنل تبلیغات تلگرام / امکانات Telegram Ads |
| /how-it-works/ | آموزش تبلیغات تلگرام / ساخت کمپین |
| /pricing/ | هزینه و تعرفه تبلیغات تلگرام / CPM |
| /faq/ | پرسش‌های تبلیغات تلگرام |
| /about/ and /contact/ | Brand trust and support |

## Production handoff

Set PUBLIC_SITE_URL to the actual canonical HTTPS origin (not a path).
Production marketing pages are indexable; when the origin is missing, canonical
and sitemap are omitted rather than constructed from a request host. Local and
staging pages, authenticated/private pages, authentication pages and draft legal
pages use noindex. Keep crawling permitted so crawlers can see noindex.
Do not publish draft legal terms as final; after legal approval, review
LEGAL_DRAFTS and update the sitemap policy. Do not submit account routes.

Verify the sitemap, canonical host, titles, status codes, mobile layout, keyboard
access and Core Web Vitals in the deployed environment. Submit the verified sitemap
in Search Console with the actual domain. Monitor impressions, clicks, search
queries and conversion only with lawful measurement. No keyword volume or ranking
is claimed without real data; no fabricated reviews, testimonials or official
partnership claims. FAQ markup is not used to promise rich results.

Reference: https://developers.google.com/search/docs/fundamentals/seo-starter-guide
Reference: https://ads.telegram.org/getting-started
Reference: https://ads.telegram.org/guidelines

Run python -m pytest tests/test_public_seo.py tests/test_final_ui_polish.py -q
on a disposable test database. Actual runtime/browser and Search Console verification
must be recorded separately. No deployment or external payment/ad writes were performed.
