class PricingError(Exception):
    """Base pricing failure."""


class NobitexAPIError(PricingError):
    pass


class StaleRateError(PricingError):
    pass


class InsufficientLiquidityError(PricingError):
    pass


class InvalidRateError(PricingError):
    pass
