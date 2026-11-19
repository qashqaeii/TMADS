class TelegramAdsError(Exception):
    """Base error for Telegram Ads integration."""


class TelegramAdsApiError(TelegramAdsError):
    """Structured API failure from the official Telegram Ads API (via telead)."""

    def __init__(
        self,
        code: str,
        *,
        description: str | None = None,
        method: str | None = None,
        retryable: bool = False,
    ) -> None:
        text = description if description and description != code else code
        super().__init__(text)
        self.api_code = code
        self.description = description
        self.method = method
        self.retryable = retryable


class TelegramAdsTransportError(TelegramAdsError):
    """Network/transport failure — not evidence of bot ineligibility."""

    retryable = True


class TelegramAdsNotConfigured(TelegramAdsError):
    pass


class TelegramAdsWriteDisabled(TelegramAdsError):
    pass
