from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class GatewayResult:
    success: bool
    provider_reference: str = ""
    raw: dict | None = None


class PaymentGateway(ABC):
    @abstractmethod
    def create_payment(self, *, amount_irr: int, callback_url: str, description: str) -> GatewayResult:
        raise NotImplementedError

    @abstractmethod
    def verify_payment(self, *, provider_reference: str, amount_irr: int) -> GatewayResult:
        raise NotImplementedError
