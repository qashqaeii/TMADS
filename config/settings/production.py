from .base import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured

# Selecting production settings must enable production safeguards regardless
# of the APP_ENV value in a development .env file.
APP_ENV = "PRODUCTION"
DEBUG = False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True

MISSING_PRODUCTION_SECRETS = []
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith(("dev-", "change-me")):
    MISSING_PRODUCTION_SECRETS.append("SECRET_KEY")
if not ALLOWED_HOSTS or any("*" in host for host in ALLOWED_HOSTS):
    MISSING_PRODUCTION_SECRETS.append("ALLOWED_HOSTS")
if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    MISSING_PRODUCTION_SECRETS.append("DATABASE_URL (PostgreSQL required)")
if PAYMENT_GATEWAY not in ("zarinpal", "zibal") or PAYMENT_FAKE_ENABLED:
    MISSING_PRODUCTION_SECRETS.append("PAYMENT_GATEWAY / PAYMENT_FAKE_ENABLED")
if PAYMENT_GATEWAY == "zibal" and (not ZIBAL_MERCHANT_ID.strip() or ZIBAL_MERCHANT_ID.strip().lower() == "zibal"):
    MISSING_PRODUCTION_SECRETS.append("ZIBAL_MERCHANT_ID (live merchant required)")
if PAYMENT_GATEWAY == "zarinpal" and (not ZARINPAL_MERCHANT_ID or ZARINPAL_SANDBOX):
    MISSING_PRODUCTION_SECRETS.append("ZARINPAL_MERCHANT_ID / ZARINPAL_SANDBOX")
if TELEGRAM_ADS_PAID_SUBMISSION_ENABLED and not TELEGRAM_ADS_WRITE_ENABLED:
    MISSING_PRODUCTION_SECRETS.append("TELEGRAM_ADS_PAID_SUBMISSION_ENABLED")
if TELEGRAM_ADS_WRITE_ENABLED and not TELEGRAM_ADS_API_TOKEN:
    MISSING_PRODUCTION_SECRETS.append("TELEGRAM_ADS_API_TOKEN")
if MISSING_PRODUCTION_SECRETS:
    raise ImproperlyConfigured(
        "Missing or invalid production configuration: "
        + ", ".join(MISSING_PRODUCTION_SECRETS)
    )
