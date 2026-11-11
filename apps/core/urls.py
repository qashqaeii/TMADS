from django.http import JsonResponse
from django.urls import path


def health_check(request):
    from django.conf import settings

    payload = {
        "status": "ok",
        "env": settings.APP_ENV,
        "telegram_ads_configured": bool(settings.TELEGRAM_ADS_API_TOKEN),
        "telegram_ads_write_enabled": settings.TELEGRAM_ADS_WRITE_ENABLED,
        "missing_production_secrets_count": len(settings.MISSING_PRODUCTION_SECRETS),
    }
    return JsonResponse(payload)


urlpatterns = [
    path("", health_check, name="health"),
]
