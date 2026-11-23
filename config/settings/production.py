from .base import *  # noqa: F403
from django.core.exceptions import ImproperlyConfigured
from urllib.parse import urlsplit

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
if PAYMENT_GATEWAY == "zibal":
    try:
        origin = urlsplit(PUBLIC_SITE_URL.strip())
        valid_origin = (origin.scheme == "https" and origin.hostname
                        and origin.hostname not in ("localhost", "127.0.0.1", "::1")
                        and not origin.username and not origin.password
                        and origin.path in ("", "/") and not origin.query and not origin.fragment
                        and not any(ch.isspace() for ch in origin.netloc) and "\\" not in origin.netloc)
        _ = origin.port
    except ValueError:
        valid_origin = False
    if not valid_origin:
        MISSING_PRODUCTION_SECRETS.append("PUBLIC_SITE_URL (registered HTTPS payment origin required)")
if PAYMENT_GATEWAY == "zarinpal" and (not ZARINPAL_MERCHANT_ID or ZARINPAL_SANDBOX):
    MISSING_PRODUCTION_SECRETS.append("ZARINPAL_MERCHANT_ID / ZARINPAL_SANDBOX")
if TELEGRAM_ADS_PAID_SUBMISSION_ENABLED and not TELEGRAM_ADS_WRITE_ENABLED:
    MISSING_PRODUCTION_SECRETS.append("TELEGRAM_ADS_PAID_SUBMISSION_ENABLED")
if TELEGRAM_ADS_WRITE_ENABLED and not TELEGRAM_ADS_API_TOKEN and len(TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY) < 32:
    MISSING_PRODUCTION_SECRETS.append("TELEGRAM_ADS_API_TOKEN or TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY (database token setup)")
if SMS_ENABLED and (SMS_PROVIDER != "faraz" or not FARAZSMS_API_KEY.strip()
        or not FARAZSMS_LINE_NUMBER.strip() or not FARAZSMS_PATTERNS["verify_mobile"].strip()
        or not FARAZSMS_OTP_ATTR.strip()):
    MISSING_PRODUCTION_SECRETS.append("SMS (Faraz credentials and verification pattern required)")
if MISSING_PRODUCTION_SECRETS:
    raise ImproperlyConfigured(
        "Missing or invalid production configuration: "
        + ", ".join(MISSING_PRODUCTION_SECRETS)
    )
