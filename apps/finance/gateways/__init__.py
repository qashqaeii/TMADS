from django.conf import settings

from .fake import FakeGateway
from .zarinpal import ZarinpalGateway


def get_payment_gateway():
    name = (settings.PAYMENT_GATEWAY or "fake").lower()
    if name == "fake":
        return FakeGateway()
    if name == "zarinpal":
        return ZarinpalGateway()
    raise NotImplementedError(f"Gateway {name} is not configured")


__all__ = ["get_payment_gateway", "FakeGateway", "ZarinpalGateway"]
