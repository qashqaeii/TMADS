class TelegramAdsError(Exception):
    pass


class TelegramAdsNotConfigured(TelegramAdsError):
    pass


class TelegramAdsWriteDisabled(TelegramAdsError):
    pass
