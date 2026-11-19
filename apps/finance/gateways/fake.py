import uuid

from django.conf import settings

from .base import GatewayResult, PaymentGateway


class FakeGateway(PaymentGateway):
    """Sandbox gateway — disabled in production unless explicitly allowed."""

    def create_payment(self, *, amount_irr: int, callback_url: str, description: str) -> GatewayResult:
        if not settings.PAYMENT_FAKE_ENABLED or settings.APP_ENV.upper() == "PRODUCTION":
            return GatewayResult(success=False, raw={"error": "fake_disabled"})
        ref = f"fake-{uuid.uuid4().hex[:12]}"
        return GatewayResult(success=True, provider_reference=ref, raw={"amount_irr": amount_irr, "description": description})

    def verify_payment(self, *, provider_reference: str, amount_irr: int) -> GatewayResult:
        if not settings.PAYMENT_FAKE_ENABLED or settings.APP_ENV.upper() == "PRODUCTION":
            return GatewayResult(success=False)
        return GatewayResult(success=True, provider_reference=provider_reference, raw={"verified": True, "amount_irr": amount_irr})
