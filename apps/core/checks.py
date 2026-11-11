from django.conf import settings
from django.core.checks import Error, register


@register()
def production_secrets_check(app_configs, **kwargs):
    errors = []
    if settings.APP_ENV == "PRODUCTION":
        for name in settings.MISSING_PRODUCTION_SECRETS:
            errors.append(
                Error(
                    f"Missing or invalid production configuration: {name}",
                    id="tmads.E001",
                )
            )
    return errors
