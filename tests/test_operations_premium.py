"""Operations UI contracts with isolated data and no external provider writes."""
import pytest
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.campaigns.models import Campaign
from apps.core.models import AuditLog
from apps.telegram_ads.models import RelatedAccountRequest


@pytest.fixture
def platform_admin(db):
    return User.objects.create_user(
        username="ops_premium_admin",
        password="Strong-test-only-pass-123!",
        role=User.Role.ADMIN,
    )


OPS_VIEWS = (
    "overview", "campaigns", "remote_operations", "related_accounts",
    "telegram_account", "refunds", "exchange_rates", "sms", "api_status",
    "release_readiness", "audit",
)


@pytest.mark.django_db
@pytest.mark.parametrize("name", OPS_VIEWS)
def test_management_pages_render_premium_shell(client, platform_admin, monkeypatch, name):
    if name == "api_status":
        class LocalTelegram:
            def get_account(self):
                return {"title": "حساب آزمایشی", "account_id": "test", "currency": "TON"}
        monkeypatch.setattr("apps.operations.views.TelegramAdsClient", LocalTelegram)
    client.force_login(platform_admin)
    response = client.get(reverse("operations:" + name))
    assert response.status_code == 200, name
    html = response.content.decode()
    assert "ga-ops-premium" in html
    assert static("css/gramads-ops-premium.css") in html
    assert '<html lang="fa" dir="rtl">' in html
    assert html.count('id="ui-confirmation"') == 1


@pytest.mark.django_db
def test_campaign_queue_search_filter_and_paging(client, platform_admin, customer_user):
    customer = customer_user.customer_profile
    for i in range(27):
        Campaign.objects.create(
            customer=customer,
            name=f"کمپین آزمایشی {i}",
            status=Campaign.Status.PENDING_REVIEW,
        )
    client.force_login(platform_admin)
    url = reverse("operations:campaigns")
    first = client.get(url)
    assert first.status_code == 200
    assert first.context["page_obj"].paginator.count == 27
    assert len(first.context["campaigns"]) == 25
    second = client.get(url, {"page": "2"})
    assert len(second.context["campaigns"]) == 2
    exact = client.get(url, {"status": "all", "q": "کمپین آزمایشی 24"})
    assert exact.context["total_results"] == 1
    assert "کمپین آزمایشی 24" in exact.content.decode()
    assert len(exact.context["status_choices"]) == len(Campaign.Status.choices)


@pytest.mark.django_db
def test_account_request_filter_returns_only_matching_clients(client, platform_admin, customer_user):
    RelatedAccountRequest.objects.create(
        customer=customer_user.customer_profile,
        status=RelatedAccountRequest.Status.PENDING,
        title="حساب درخواست آزمایشی",
        consent_at=timezone.now(),
    )
    client.force_login(platform_admin)
    url = reverse("operations:related_accounts")
    yes = client.get(url, {"status": "pending", "q": "درخواست آزمایشی"})
    assert yes.status_code == 200
    assert yes.context["page_obj"].paginator.count == 1
    no = client.get(url, {"status": "provisioned", "q": "درخواست آزمایشی"})
    assert no.context["page_obj"].paginator.count == 0
    assert "درخواستی ثبت نشده" in no.content.decode()


@pytest.mark.django_db
def test_audit_log_search_type_and_paginated_timeline(client, platform_admin):
    for i in range(31):
        AuditLog.objects.create(
            actor=platform_admin,
            action="ops.approve",
            entity_type="campaign",
        )
    AuditLog.objects.create(actor=platform_admin, action="refund.review", entity_type="refund")
    client.force_login(platform_admin)
    url = reverse("operations:audit")
    first = client.get(url, {"entity": "campaign"})
    assert first.status_code == 200
    assert first.context["page_obj"].paginator.count == 31
    assert len(first.context["logs"]) == 30
    second = client.get(url, {"entity": "campaign", "page": 2})
    assert len(second.context["logs"]) == 1
    refund = client.get(url, {"entity": "refund", "q": platform_admin.username})
    assert refund.context["page_obj"].paginator.count == 1


@pytest.mark.django_db
def test_customer_cannot_enter_any_premium_operations_view(client, customer_user):
    client.force_login(customer_user)
    for name in ("overview", "campaigns", "refunds", "audit"):
        assert client.get(reverse("operations:" + name)).status_code == 403
