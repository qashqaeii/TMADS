from django.conf import settings


def site_settings(request):
    unread = 0
    profile = getattr(request, "customer_profile", None)
    wallet_hint = None
    if profile is not None:
        from apps.finance.services import ensure_wallet
        from apps.notifications.models import Notification

        unread = Notification.objects.filter(customer=profile, is_read=False).count()
        wallet = ensure_wallet(profile)
        wallet_hint = {
            "available_toman": wallet.available_irr // 10,
            "reserved_toman": wallet.reserved_irr // 10,
        }

    return {
        "PRODUCT_NAME": settings.PRODUCT_NAME,
        "PRODUCT_TAGLINE": settings.PRODUCT_TAGLINE,
        "APP_ENV": settings.APP_ENV,
        "unread_notifications": unread,
        "wallet_hint": wallet_hint,
        "customer_profile": profile,
    }
