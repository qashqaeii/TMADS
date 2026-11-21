"""Operator entry points and role-specific navigation regressions."""
import pytest
from django.urls import reverse
from apps.accounts.models import User


@pytest.mark.django_db
@pytest.mark.parametrize("manager_superuser", [False, True])
def test_management_login_lands_in_operations_without_customer_profile(client, manager_superuser):
    if manager_superuser:
        manager = User.objects.create_superuser(
            username="ops_super", password="safe-test-password-123", email="ops@example.invalid",
            role=User.Role.ADMIN,
        )
    else:
        manager = User.objects.create_user(
            username="ops_manager", password="safe-test-password-123", role=User.Role.ADMIN,
        )
    assert not hasattr(manager, "customer_profile")
    response = client.post(reverse("accounts:login"), {
        "username": manager.username, "password": "safe-test-password-123",
    })
    assert response.status_code == 302
    assert response.url == reverse("operations:overview")
    html = client.get(response.url)
    assert html.status_code == 200
    body = html.content.decode()
    assert 'class="app-layout ui-shell"' in body
    assert "مرکز عملیات" in body
    assert reverse("accounts:profile") not in body
    assert reverse("campaigns:wizard_new") not in body


@pytest.mark.django_db
def test_authenticated_operator_login_and_public_ctas_use_operations(client):
    manager = User.objects.create_user(
        username="ops_redirect", password="safe-test-password-123", role=User.Role.ADMIN,
    )
    client.force_login(manager)
    assert client.get(reverse("accounts:login")).url == reverse("operations:overview")
    for path in ("/", "/features/"):
        response = client.get(path)
        assert response.status_code == 200
        assert reverse("operations:overview") in response.content.decode()
    assert client.get(reverse("dashboard:home")).status_code == 403


@pytest.mark.django_db
def test_customers_still_land_on_customer_dashboard(client, customer_user):
    response = client.post(reverse("accounts:login"), {
        "username": customer_user.username, "password": "pass1234",
    })
    assert response.status_code == 302
    assert response.url == reverse("dashboard:home")
    assert client.get(response.url).status_code == 200
