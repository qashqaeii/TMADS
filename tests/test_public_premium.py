"""Public premium shell and interaction markup regression checks."""
from html.parser import HTMLParser

import pytest
from django.templatetags.static import static
from django.urls import reverse


class PublicMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.anchors = []
        self.styles = []
        self.scripts = []
        self.body_classes = []
        self.h1_count = 0

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        if attr.get("id"):
            self.ids.add(attr["id"])
        if tag == "a" and attr.get("href", "").startswith("#"):
            self.anchors.append(attr["href"][1:])
        if tag == "link" and attr.get("rel") == "stylesheet":
            self.styles.append(attr.get("href"))
        if tag == "script":
            self.scripts.append(attr.get("src"))
        if tag == "body":
            self.body_classes = attr.get("class", "").split()
        if tag == "h1":
            self.h1_count += 1


@pytest.mark.django_db
@pytest.mark.parametrize("route, page_class", [
    ("public:home", "pp-home"), ("public:features", "pp-features"),
    ("public:how_it_works", "pp-how-it-works"), ("public:pricing", "pp-pricing"),
    ("public:faq", "pp-faq"), ("public:about", "pp-about"), ("public:contact", "pp-contact"),
    ("public:terms", "pp-legal-page"), ("public:privacy", "pp-legal-page"),
    ("public:refund", "pp-legal-page"), ("public:content_policy", "pp-legal-page"),
    ("accounts:login", "pp-login"), ("accounts:register", "pp-register"),
    ("accounts:password_reset", "pp-password-reset"),
    ("accounts:password_reset_done", "pp-password-reset-done"),
    ("accounts:password_reset_complete", "pp-password-reset-complete"),
])
def test_premium_pages_render(client, route, page_class):
    response = client.get(reverse(route))
    assert response.status_code == 200
    parser = PublicMarkup()
    parser.feed(response.content.decode())
    assert "public-premium" in parser.body_classes
    assert page_class in parser.body_classes
    assert parser.h1_count == 1
    assert static("css/public-premium.css") in parser.styles
    assert static("js/public-premium.js") in parser.scripts
    assert set(filter(None, parser.anchors)) <= parser.ids


@pytest.mark.django_db
def test_public_faq_search_progressively_enhanced(client):
    response = client.get(reverse("public:faq"))
    assert b"data-pp-faq-search" in response.content
    assert b'data-pp-faq-count role="status"' in response.content
    assert response.content.count(b"<details") > 10


@pytest.mark.django_db
def test_login_password_visibility_does_not_change_submission(client):
    response = client.get(reverse("accounts:login"))
    assert b'type="password" name="password" id="id_password"' in response.content
    assert b'data-pp-password-toggle aria-controls="id_password"' in response.content
    assert b'csrfmiddlewaretoken' in response.content


@pytest.mark.django_db
def test_invalid_reset_link_uses_recovery_shell(client):
    response = client.get(reverse("accounts:password_reset_confirm", args=["invalid", "bad-token"]))
    assert response.status_code == 200
    assert b"pp-password-reset-confirm" in response.content
    assert b"pp-auth-recovery" in response.content
