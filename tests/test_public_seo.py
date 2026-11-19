"""Public search and conversion regressions; no live external calls."""
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

import pytest
from django.urls import reverse

from apps.public.seo import PAGES, LEGAL_DRAFTS


class PageHead(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_count = 0
        self.h1_count = 0
        self.meta = {}
        self.canonical = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.title_count += 1
        if tag == "h1":
            self.h1_count += 1
        if tag == "meta" and "name" in attrs:
            self.meta.setdefault(attrs["name"], []).append(attrs.get("content", ""))
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical.append(attrs.get("href"))


def read_head(response):
    assert response.status_code == 200
    parser = PageHead()
    parser.feed(response.content.decode())
    return parser


@pytest.mark.django_db
@pytest.mark.parametrize("name", list(PAGES))
def test_public_page_metadata(client, settings, name):
    settings.APP_ENV = "PRODUCTION"
    settings.PUBLIC_SITE_URL = "https://example.test"
    path = reverse("public:" + name)
    page = read_head(client.get(path + "?utm_source=sample"))
    assert page.title_count == page.h1_count == 1
    assert page.meta["description"] == [PAGES[name][1]]
    if name in LEGAL_DRAFTS:
        assert page.meta["robots"] == ["noindex, follow"]
        assert not page.canonical
    else:
        assert page.meta["robots"] == ["index, follow"]
        assert page.canonical == ["https://example.test" + path]


@pytest.mark.django_db
@pytest.mark.parametrize("route", [
    "accounts:login", "accounts:register", "accounts:password_reset",
    "accounts:password_reset_done", "accounts:password_reset_complete",
])
def test_auth_pages_not_indexed(client, settings, route):
    settings.APP_ENV = "PRODUCTION"
    settings.PUBLIC_SITE_URL = "https://example.test"
    page = read_head(client.get(reverse(route)))
    assert page.meta["robots"] == ["noindex, follow"]
    assert not page.canonical


@pytest.mark.django_db
def test_sitemap_matches_indexable_pages(client, settings):
    settings.APP_ENV = "PRODUCTION"
    settings.PUBLIC_SITE_URL = "https://example.test"
    response = client.get(reverse("public:sitemap"))
    assert response.status_code == 200
    root = ET.fromstring(response.content)
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    found = {element.text for element in root.findall("s:url/s:loc", ns)}
    assert found == {"https://example.test" + reverse("public:" + name)
                     for name in PAGES if name not in LEGAL_DRAFTS}
    robots = client.get(reverse("public:robots"))
    assert b"Sitemap: https://example.test/sitemap.xml" in robots.content


@pytest.mark.django_db
def test_staging_noindex_and_missing_origin_no_guessed_canonical(client, settings):
    settings.APP_ENV = "STAGING"
    settings.PUBLIC_SITE_URL = "https://example.test"
    page = read_head(client.get(reverse("public:home")))
    assert page.meta["robots"] == ["noindex, follow"]
    assert client.get(reverse("public:sitemap")).status_code == 404
    settings.APP_ENV = "PRODUCTION"
    settings.PUBLIC_SITE_URL = ""
    page = read_head(client.get(reverse("public:home")))
    assert page.meta["robots"] == ["index, follow"]
    assert not page.canonical
    assert client.get(reverse("public:sitemap")).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("name,section_id", [
    ("home", "telegram-ads-guide"), ("features", "advertiser-toolkit"),
    ("how_it_works", "campaign-playbook"), ("pricing", "budget-decisions"),
    ("faq", "faq-deeper"), ("about", "product-principles"), ("contact", "support-guide"),
])
def test_public_editorial_content_and_structured_data(client, settings, name, section_id):
    import json
    import re

    settings.APP_ENV = "PRODUCTION"
    settings.PUBLIC_SITE_URL = "https://example.test"
    response = client.get(reverse("public:" + name))
    assert response.status_code == 200
    html = response.content.decode()
    assert f'id="{section_id}"' in html
    assert 'aria-label="مطالعه بیشتر"' in html
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert match
    data = json.loads(match.group(1))
    graph = data["@graph"]
    assert graph[0]["@type"] == ("WebSite" if name == "home" else "BreadcrumbList")
    if name != "home":
        assert graph[0]["itemListElement"][-1]["item"] == "https://example.test" + reverse("public:" + name)


@pytest.mark.django_db
def test_schema_is_not_published_for_drafts_or_staging(client, settings):
    settings.PUBLIC_SITE_URL = "https://example.test"
    settings.APP_ENV = "PRODUCTION"
    assert b'application/ld+json' not in client.get(reverse("public:terms")).content
    assert b'application/ld+json' not in client.get(reverse("accounts:login")).content
    settings.APP_ENV = "STAGING"
    assert b'application/ld+json' not in client.get(reverse("public:home")).content
