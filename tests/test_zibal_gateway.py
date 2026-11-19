"""Offline Zibal contract tests: no network access and no real payments."""
from unittest.mock import patch
import httpx
import pytest
from apps.finance.gateways.zibal import ZibalGateway, track_id


@pytest.fixture
def gateway(settings):
    settings.APP_ENV = "LOCAL"
    settings.ZIBAL_MERCHANT_ID = "zibal"
    return ZibalGateway()


def test_request_contract_and_fixed_start_url(gateway):
    with patch("apps.finance.gateways.zibal.httpx.Client") as client:
        post = client.return_value.__enter__.return_value.post
        post.return_value.json.return_value = {"result": 100, "trackId": 45123}
        result = gateway.create_payment(amount_irr=120000, callback_url="https://example.test/return/",
                                        description="topup-123")
        assert result.success and result.provider_reference == "45123"
        assert result.raw["redirect_url"] == "https://gateway.zibal.ir/start/45123"
        assert post.call_args.args[0] == "https://gateway.zibal.ir/v1/request"
        assert post.call_args.kwargs["json"] == {
            "merchant": "zibal", "amount": 120000, "callbackUrl": "https://example.test/return/",
            "description": "topup-123", "orderId": "123",
        }


@pytest.mark.parametrize("response", [{"result": 102}, {"result": 100}, {"result": 100, "trackId": True},
    {"result": 100, "trackId": "https://evil.test"}, {"result": 100, "trackId": 0}])
def test_request_rejects_no_valid_track(gateway, response):
    with patch.object(gateway, "_post", return_value=response):
        assert not gateway.create_payment(amount_irr=10000, callback_url="https://example.test/",
                                          description="test").success


@pytest.mark.parametrize("value", [None, False, -1, 0, 1.5, "abc", "1/2", "١", "9"*33])
def test_track_id_rejects_invalid_values(value):
    assert not track_id(value)


@pytest.mark.parametrize("response", [
    {"result": 100, "amount": 120001, "refNumber": 123},
    {"result": 100, "refNumber": 123},
    {"result": 100, "amount": 120000},
    {"result": 100, "amount": 120000, "refNumber": True},
    {"result": 100, "amount": 120000.0, "refNumber": 123},
    {"result": 100, "amount": 120000, "refNumber": 123, "trackId": 999},
    {"result": 202, "amount": 120000, "refNumber": 123},
    {"error": "gateway_unavailable"},
])
def test_verify_fails_closed(gateway, response):
    with patch.object(gateway, "_post", return_value=response):
        assert not gateway.verify_payment(provider_reference="45123", amount_irr=120000).success


def test_verify_request_and_receipt(gateway):
    with patch.object(gateway, "_post", return_value={"result": 100, "amount": 120000,
            "refNumber": 987654, "cardNumber": "never persist"}) as post:
        result = gateway.verify_payment(provider_reference="45123", amount_irr=120000)
        post.assert_called_once_with("verify", {"trackId": 45123})
        assert result.success and result.raw["bank_reference"] == "987654"
        assert "cardNumber" not in result.raw


@pytest.mark.parametrize("status,amount,expected", [(1, 120000, True), (2, 120000, False),
    (1, 120001, False), (1, None, False)])
def test_already_verified_requires_authenticated_inquiry(gateway, status, amount, expected):
    with patch.object(gateway, "_post", side_effect=[
        {"result": 201}, {"result": 100, "status": status, "amount": amount, "refNumber": 123}
    ]) as post:
        result = gateway.verify_payment(provider_reference="45123", amount_irr=120000)
        assert result.success is expected
        assert post.call_args.args == ("inquiry", {"trackId": 45123})


def test_transport_timeout_is_safe(gateway):
    with patch("apps.finance.gateways.zibal.httpx.Client") as client:
        client.return_value.__enter__.return_value.post.side_effect = httpx.ReadTimeout("timeout")
        assert not gateway.verify_payment(provider_reference="45123", amount_irr=120000).success


def test_test_merchant_blocked_in_production(settings):
    settings.APP_ENV = "PRODUCTION"
    settings.ZIBAL_MERCHANT_ID = " zibal "
    with patch("apps.finance.gateways.zibal.httpx.Client") as client:
        assert not ZibalGateway().verify_payment(provider_reference="45123", amount_irr=120000).success
        client.assert_not_called()
