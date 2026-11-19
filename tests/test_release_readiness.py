import pytest
from django.urls import reverse
from apps.operations.release_checks import readiness_summary


@pytest.mark.django_db
def test_readiness_never_claims_launch_when_gates_are_off(settings):
    settings.TELEGRAM_ADS_WRITE_ENABLED=False
    settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED=False
    settings.PAYMENT_FAKE_ENABLED=True
    summary=readiness_summary()
    assert summary["can_launch"] is False
    assert summary["blocked"]>=1
    assert any(x.key=="integration_tests" and x.state=="pending" for x in summary["items"])
    assert all("secret" not in x.explanation.lower() for x in summary["items"])


@pytest.mark.django_db
def test_readiness_is_not_public(client, customer_user):
    client.force_login(customer_user)
    response=client.get(reverse("operations:release_readiness"))
    assert response.status_code!=200
