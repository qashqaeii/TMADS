from .base import *  # noqa: F403

DEBUG = True

if APP_ENV == "LOCAL":  # noqa: F405
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Dev without Docker: avoid hard dependency on Redis for runserver
CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
