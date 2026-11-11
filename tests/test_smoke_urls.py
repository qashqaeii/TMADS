import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_public_pages_ok(client):
    for name in ("public:home", "public:terms", "public:privacy", "public:pricing"):
        response = client.get(reverse(name))
        assert response.status_code == 200


@pytest.mark.django_db
def test_app_shell_routes_auth_redirect(client):
    for name in (
        "dashboard:home",
        "finance:wallet",
        "finance:invoices",
        "campaigns:list",
        "policies:ad_policies",
    ):
        response = client.get(reverse(name))
        assert response.status_code == 302
