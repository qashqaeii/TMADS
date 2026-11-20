"""Legal pages retain original document wording and native anchors."""
from html.parser import HTMLParser

import pytest
from django.templatetags.static import static
from django.urls import reverse

from apps.public.legal_content import load_legal_text, structure_legal_text


class LegalDocument(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.parts = []
        self.tag = None
        self.current = []

    def handle_starttag(self, tag, attrs):
        if tag == "article" and dict(attrs).get("id") == "legal-document":
            self.inside = True
        if self.inside and tag in {"p", "li"}:
            self.tag = tag
            self.current = []

    def handle_data(self, data):
        if self.inside and self.tag:
            self.current.append(data)

    def handle_endtag(self, tag):
        if self.inside and self.tag == tag:
            self.parts.append("".join(self.current).strip())
            self.tag = None
        if tag == "article":
            self.inside = False


@pytest.mark.django_db
@pytest.mark.parametrize("route,slug,count", [
    ("terms", "terms", 4), ("privacy", "privacy", 4),
    ("refund", "refund", 3), ("content_policy", "content", 0),
])
def test_legal_document_content_and_navigation(client, route, slug, count):
    response = client.get(reverse("public:" + route))
    assert response.status_code == 200
    html = response.content.decode()
    assert "orbit-legal" in html
    assert static("css/legal-orbit.css") in html
    assert static("js/legal-orbit.js") in html
    assert html.count('class="lg-clause"') == count
    assert html.count('aria-current="page"') >= 1
    assert 'data-legal-print' in html
    assert 'id="legal-document"' in html
    original = load_legal_text(slug)
    doc = structure_legal_text(original)
    blocks = doc["intro"] + [b for s in doc["sections"] for b in s["blocks"]]
    expected = [part for b in blocks for part in (b["items"] if b["kind"] == "list" else [b["text"]])]
    parser = LegalDocument()
    parser.feed(html)
    assert parser.parts == ["سند حقوقی گرام‌ادز"] + expected
    assert doc["heading"] in html
    for section in doc["sections"]:
        assert f'id="{section["id"]}"' in html
        assert f'href="#{section["id"]}"' in html
    assert "# " not in "".join(parser.parts)
    assert response.context["legal_art"]
    assert response.context["legal_support_art"]


def test_legal_parser_lists_and_untrusted_text():
    source = "# سند\n\nمقدمه\n\n## بخش\n\n- اول\n- <script>alert(1)</script>\n\nآخر"
    doc = structure_legal_text(source)
    assert doc["heading"] == "سند"
    assert doc["intro"] == [{"kind": "paragraph", "text": "مقدمه"}]
    assert doc["sections"][0]["blocks"] == [
        {"kind": "list", "items": ["اول", "<script>alert(1)</script>"]},
        {"kind": "paragraph", "text": "آخر"},
    ]


@pytest.mark.django_db
def test_legal_render_escapes_markup(client, monkeypatch):
    monkeypatch.setattr("apps.public.views.load_legal_text", lambda slug: "# سند\n\n<script>alert(1)</script>")
    html = client.get(reverse("public:terms")).content.decode()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<script>alert(1)</script>" not in html
    other = client.get(reverse("public:faq")).content.decode()
    assert static("css/legal-orbit.css") not in other
    assert static("js/legal-orbit.js") not in other
