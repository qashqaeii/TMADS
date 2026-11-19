"""Offline contract and failure mode tests, no actual SMS."""
from datetime import timedelta
from unittest.mock import patch
import httpx
import pytest
from django.urls import reverse
from django.utils import timezone
from apps.accounts.models import User
from apps.accounts.sms_views import issue, confirm
from apps.notifications.faraz import normalize_mobile, send_pattern, SmsResult
from apps.notifications.models import SmsContact, SmsOtp, SmsOutbox
from apps.notifications.sms import enqueue_sms, dispatch_one, dispatch_pending


@pytest.fixture
def sms(settings):
    settings.SMS_ENABLED = True
    settings.SMS_PROVIDER = "faraz"
    settings.FARAZSMS_API_KEY = "test-only"
    settings.FARAZSMS_LINE_NUMBER = "5000123"
    settings.FARAZSMS_OTP_LINE_NUMBER = "9000123"
    settings.FARAZSMS_PATTERNS = {k: "pattern-test" for k in ("verify_mobile", "wallet_credit", "budget_low", "campaign_status")}
    settings.FARAZSMS_OTP_ATTR = "code"


@pytest.mark.parametrize("raw,expected", [("۰۹۱۲۳۴۵۶۷۸۹", "09123456789"), ("+98 9123456789", "09123456789"),
    ("00989123456789", "09123456789"), ("0912345678", ""), ("12345678901", ""), ("", "")])
def test_normalize_mobile(raw, expected):
    assert normalize_mobile(raw) == expected


def test_faraz_pattern_contract(sms):
    with patch("apps.notifications.faraz.httpx.Client") as mock:
        request = mock.return_value.__enter__.return_value.request
        request.return_value.status_code = 201
        request.return_value.json.return_value = {"status": "success", "data": 12345}
        result = send_pattern("09123456789", "verify_mobile", {"code": "123456"})
        assert result == SmsResult("accepted", "12345")
        args, kwargs = request.call_args
        assert args == ("POST", "https://api.iranpayamak.com/ws/v1/sms/pattern")
        assert kwargs["headers"]["Api-Key"] == "test-only"
        assert kwargs["json"] == {"code": "pattern-test", "recipient": "09123456789", "attributes": {"code": "123456"},
                                  "line_number": "9000123", "number_format": "english"}


@pytest.mark.parametrize("status,payload,expected", [(403, {}, "failed"), (429, {}, "failed"), (503, {}, "unknown"),
    (201, {"status": "error"}, "failed"), (201, {"unrecognized": True}, "unknown")])
def test_provider_failure_not_success(sms, status, payload, expected):
    with patch("apps.notifications.faraz.httpx.Client") as mock:
        request = mock.return_value.__enter__.return_value.request
        request.return_value.status_code = status
        request.return_value.json.return_value = payload
        assert send_pattern("09123456789", "wallet_credit", {"amount": "1000"}).state == expected


def test_timeout_unknown_no_retry(sms):
    with patch("apps.notifications.faraz.httpx.Client") as mock:
        request = mock.return_value.__enter__.return_value.request
        request.side_effect = httpx.ReadTimeout("timeout")
        assert send_pattern("09123456789", "wallet_credit", {}).state == "unknown"
        request.assert_called_once()


@pytest.mark.django_db
def test_otp_one_time_and_not_plaintext(sms, customer_profile):
    with patch("apps.accounts.sms_views.secrets.randbelow", return_value=123456), patch(
        "apps.accounts.sms_views.send_pattern", return_value=SmsResult("accepted")) as send:
        assert issue(customer_profile, "09123456789") == "sent"
        assert issue(customer_profile, "09123456789") == "rate"
        send.assert_called_once()
    challenge = SmsOtp.objects.get(customer=customer_profile)
    assert challenge.digest != "123456" and "123456" not in challenge.digest
    assert not confirm(customer_profile, "111111")
    assert confirm(customer_profile, "۱۲۳۴۵۶")
    assert not confirm(customer_profile, "123456")
    assert SmsContact.objects.get(customer=customer_profile).phone == "09123456789"


@pytest.mark.django_db
def test_failed_otp_cannot_confirm(sms, customer_profile):
    with patch("apps.accounts.sms_views.secrets.randbelow", return_value=123456), patch(
        "apps.accounts.sms_views.send_pattern", return_value=SmsResult("unknown")):
        assert issue(customer_profile, "09123456789") == "unavailable"
    assert not confirm(customer_profile, "123456")
    assert not SmsContact.objects.exists()


@pytest.mark.django_db
def test_expired_and_locked_otp(sms, customer_profile):
    with patch("apps.accounts.sms_views.secrets.randbelow", return_value=123456), patch(
        "apps.accounts.sms_views.send_pattern", return_value=SmsResult("accepted")):
        assert issue(customer_profile, "09123456789") == "sent"
    for _ in range(5):
        assert not confirm(customer_profile, "111111")
    assert not confirm(customer_profile, "123456")
    SmsOtp.objects.filter(customer=customer_profile).update(created_at=timezone.now()-timedelta(hours=2))
    with patch("apps.accounts.sms_views.secrets.randbelow", return_value=123456), patch(
        "apps.accounts.sms_views.send_pattern", return_value=SmsResult("accepted")):
        assert issue(customer_profile, "09123456789") == "sent"
    SmsOtp.objects.filter(consumed=False).update(expires_at=timezone.now()-timedelta(seconds=1))
    assert not confirm(customer_profile, "123456")


@pytest.mark.django_db
def test_only_verified_opted_in_and_deduplicated(sms, customer_profile):
    assert enqueue_sms(customer_profile, "wallet_credit", "evt", {"amount": "1000"}) is None
    contact = SmsContact.objects.create(customer=customer_profile, phone="09123456789")
    first = enqueue_sms(customer_profile, "wallet_credit", "evt", {"amount": "1000"})
    assert enqueue_sms(customer_profile, "wallet_credit", "evt", {"amount": "9999"}).pk == first.pk
    with patch("apps.notifications.sms.send_pattern", return_value=SmsResult("accepted", "123")) as send:
        dispatch_one(first.pk)
        dispatch_one(first.pk)
        send.assert_called_once()
    first.refresh_from_db()
    assert first.status == "accepted"
    assert first.attributes == {"amount": "1000"}
    second = enqueue_sms(customer_profile, "wallet_credit", "evt2", {"amount": "1000"})
    contact.enabled = False
    contact.save()
    with patch("apps.notifications.sms.send_pattern") as send:
        dispatch_one(second.pk)
        send.assert_not_called()
    second.refresh_from_db()
    assert second.status == "skipped"


@pytest.mark.django_db
def test_interrupted_worker_not_resubmitted(sms, customer_profile):
    SmsContact.objects.create(customer=customer_profile, phone="09123456789")
    row = enqueue_sms(customer_profile, "budget_low", "low", {})
    SmsOutbox.objects.filter(pk=row.pk).update(status="sending", updated_at=timezone.now()-timedelta(minutes=20))
    with patch("apps.notifications.sms.send_pattern") as send:
        assert dispatch_pending() == 0
        send.assert_not_called()
    row.refresh_from_db()
    assert row.status == "unknown"


@pytest.mark.django_db
def test_dashboard_access_and_masked_log(client, customer_user, sms):
    customer = customer_user.customer_profile
    SmsContact.objects.create(customer=customer, phone="09123456789")
    enqueue_sms(customer, "wallet_credit", "event", {"amount": "1000"})
    client.force_login(customer_user)
    url = reverse("operations:sms")
    assert client.get(url).status_code == 403
    assert client.get(reverse("accounts:mobile_settings")).status_code == 200
    admin = User.objects.create_user(username="sms-admin", role=User.Role.ADMIN)
    client.force_login(admin)
    with patch("apps.operations.sms_views.get_balance") as balance:
        response = client.get(url)
        assert response.status_code == 200
        balance.assert_not_called()
    assert b"09123456789" not in response.content and b"test-only" not in response.content
    assert "no-store" in response["Cache-Control"]
