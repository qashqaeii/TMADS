"""Public support center: native links, access control and local artwork."""
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import pytest
from django.templatetags.static import static
from django.urls import reverse

from apps.public.views import CONTACT_ART


@pytest.mark.django_db
def test_contact_orbit_content_and_scope(client, customer_user):
    response = client.get(reverse("public:contact"))
    assert response.status_code == 200
    html = response.content.decode()
    assert "orbit-contact" in html
    assert html.count("<h1") == 1
    assert html.count('class="ct-glass ct-topic"') == 3
    assert html.count('class="ct-glass ct-guide-card"') == 3
    assert "اطلاعات حساس را ارسال نکنید" in html
    assert static("css/contact-orbit.css") in html
    assert static("js/contact-orbit.js") in html
    for section in ("contact-topics", "contact-ticket", "support-guide"):
        assert f'id="{section}"' in html
        assert f'href="#{section}"' in html
    for role in CONTACT_ART:
        assert f'data-contact-art="{role}"' in html
        assert response.context["contact_art"][role] in html
    ticket_url = reverse("support:create")
    assert f'href="{ticket_url}"' in html
    redirect = client.get(ticket_url)
    assert redirect.status_code == 302
    assert parse_qs(urlsplit(redirect.url).query)["next"] == [ticket_url]
    for route in ("public:home", "public:faq", "public:terms", "public:about"):
        other = client.get(reverse(route)).content.decode()
        assert static("css/contact-orbit.css") not in other
        assert static("js/contact-orbit.js") not in other
    client.force_login(customer_user)
    signed_in = client.get(reverse("public:contact")).content.decode()
    assert f'href="{ticket_url}"' in signed_in
    assert f'href="{reverse("support:list")}"' in signed_in
    assert client.get(ticket_url).status_code == 200


@pytest.mark.django_db
def test_contact_art_local_preferred_and_fallback(client):
    with patch("apps.public.views.finders.find", return_value="present"):
        response = client.get(reverse("public:contact"))
        for role, (path, _) in CONTACT_ART.items():
            assert response.context["contact_art"][role] == static(path)
    with patch("apps.public.views.finders.find", return_value=None), patch(
        "apps.public.views.feature_asset", return_value="/static/fallback.webp"
    ):
        response = client.get(reverse("public:contact"))
        assert set(response.context["contact_art"].values()) == {"/static/fallback.webp"}
