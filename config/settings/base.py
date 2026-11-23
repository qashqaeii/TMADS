from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    TELEGRAM_ADS_WRITE_ENABLED=(bool, False),
    TELEGRAM_ADS_PAID_SUBMISSION_ENABLED=(bool, False),
    PAYMENT_FAKE_ENABLED=(bool, True),
    PLATFORM_SERVICE_FEE_PERCENT=(int, 5),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

APP_ENV = env("APP_ENV", default="LOCAL")
# Canonical public HTTPS origin; no request-host fallback.
PUBLIC_SITE_URL = env("PUBLIC_SITE_URL", default="")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "rest_framework",
    "django_celery_beat",
    "django_celery_results",
    "apps.core",
    "apps.accounts",
    "apps.public",
    "apps.dashboard",
    "apps.campaigns",
    "apps.finance",
    "apps.telegram_ads",
    "apps.notifications",
    "apps.support",
    "apps.operations",
    "apps.policies",
    "apps.ai",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.CustomerContextMiddleware",
    "apps.core.middleware.AuthRateLimitMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site_settings",
                "apps.public.seo.metadata",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "accounts.User"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fa"
TIME_ZONE = "Asia/Tehran"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "public:home"

REDIS_URL = env("REDIS_URL", default="redis://127.0.0.1:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="django-db")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    "dispatch-transactional-sms": {"task": "apps.notifications.tasks.dispatch_sms", "schedule": 60.0},
    "sync-active-ad-stats-hourly": {
        "task": "apps.telegram_ads.tasks.task_sync_active_ad_stats",
        "schedule": 3600.0,
    },
    "budget-alerts-hourly": {
        "task": "apps.telegram_ads.tasks.task_emit_budget_alerts",
        "schedule": 3600.0,
    },
    "sync-remote-ads-list-daily": {
        "task": "apps.telegram_ads.tasks.task_sync_remote_ads",
        "schedule": 86400.0,
    },
    "refresh-ton-exchange-rate": {
        "task": "apps.finance.tasks.refresh_ton_exchange_rate",
        "schedule": 60.0,
    },
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")

# Telegram Ads
TELEGRAM_ADS_API_TOKEN = env("TELEGRAM_ADS_API_TOKEN", default="")
TELEGRAM_ADS_WRITE_ENABLED = env("TELEGRAM_ADS_WRITE_ENABLED")
TELEGRAM_ADS_PAID_SUBMISSION_ENABLED = env("TELEGRAM_ADS_PAID_SUBMISSION_ENABLED")
TELEGRAM_ADS_MEDIA_UPLOAD_ENABLED = env.bool("TELEGRAM_ADS_MEDIA_UPLOAD_ENABLED", default=False)
TELEGRAM_ADS_RELATED_ACCOUNTS_ENABLED = env.bool("TELEGRAM_ADS_RELATED_ACCOUNTS_ENABLED", default=False)
TELEGRAM_ADS_WEBSITE_ENABLED = env.bool("TELEGRAM_ADS_WEBSITE_ENABLED", default=False)
TELEGRAM_ADS_CUSTOMER_ASSETS_ENABLED = env.bool("TELEGRAM_ADS_CUSTOMER_ASSETS_ENABLED", default=False)
TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED = env.bool("TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED", default=False)
# Stable high-entropy server-only secret for Fernet token encryption. Never reuse SECRET_KEY.
TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY = env("TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY", default="")
# Similar Bots — catalog recommendations gated by official getTargetBot (no web-panel session).
SIMILAR_BOTS_ENABLED = env.bool("SIMILAR_BOTS_ENABLED", default=True)
SIMILAR_CHANNELS_ENABLED = env.bool("SIMILAR_CHANNELS_ENABLED", default=True)

# Transactional SMS — off until separate GramAds credentials/patterns are approved.
SMS_ENABLED = env.bool("SMS_ENABLED", default=False)
SMS_PROVIDER = env("SMS_PROVIDER", default="console").strip().lower()
FARAZSMS_API_KEY = env("FARAZSMS_API_KEY", default="")
FARAZSMS_LINE_NUMBER = env("FARAZSMS_LINE_NUMBER", default="")
FARAZSMS_OTP_LINE_NUMBER = env("FARAZSMS_OTP_LINE_NUMBER", default="")
FARAZSMS_PATTERNS = {
    "verify_mobile": env("FARAZSMS_PATTERN_VERIFY_MOBILE", default=""),
    "wallet_credit": env("FARAZSMS_PATTERN_WALLET_CREDIT", default=""),
    "budget_low": env("FARAZSMS_PATTERN_BUDGET_LOW", default=""),
    "campaign_status": env("FARAZSMS_PATTERN_CAMPAIGN_STATUS", default=""),
}
FARAZSMS_OTP_ATTR = env("FARAZSMS_OTP_ATTR", default="code")
# ArvanCloud AIaaS — server-side only; calls are always explicitly user-triggered.
ARVAN_AI_ENABLED = env.bool("ARVAN_AI_ENABLED", default=False)
ARVAN_AI_BASE_URL = env("ARVAN_AI_BASE_URL", default="")
ARVAN_AI_API_KEY = env("ARVAN_AI_API_KEY", default="")
ARVAN_AI_MODEL = env("ARVAN_AI_MODEL", default="Gemini-2.5-Flash-lite")
ARVAN_AI_FALLBACK_MODEL = env("ARVAN_AI_FALLBACK_MODEL", default="")
ARVAN_AI_TIMEOUT_SECONDS = env.int("ARVAN_AI_TIMEOUT_SECONDS", default=10)
ARVAN_AI_MAX_RETRIES = env.int("ARVAN_AI_MAX_RETRIES", default=1)
ARVAN_AI_TEMPERATURE = env.float("ARVAN_AI_TEMPERATURE", default=0.2)
ARVAN_AI_MAX_TOKENS = env.int("ARVAN_AI_MAX_TOKENS", default=900)
ARVAN_AI_USER_DAILY_LIMIT = env.int("ARVAN_AI_USER_DAILY_LIMIT", default=10)
ARVAN_AI_GLOBAL_DAILY_LIMIT = env.int("ARVAN_AI_GLOBAL_DAILY_LIMIT", default=200)
ARVAN_AI_FEATURE_DAILY_LIMITS = {
    "planner": env.int("ARVAN_AI_PLANNER_DAILY_LIMIT", default=3),
    "creative": env.int("ARVAN_AI_CREATIVE_DAILY_LIMIT", default=4),
    "analysis": env.int("ARVAN_AI_ANALYSIS_DAILY_LIMIT", default=3),
    "optimization": env.int("ARVAN_AI_OPTIMIZATION_DAILY_LIMIT", default=3),
}
# Payments
PAYMENT_GATEWAY = env("PAYMENT_GATEWAY", default="fake")
PAYMENT_FAKE_ENABLED = env("PAYMENT_FAKE_ENABLED")
ZIBAL_MERCHANT_ID = env("ZIBAL_MERCHANT_ID", default="")
ZARINPAL_MERCHANT_ID = env("ZARINPAL_MERCHANT_ID", default="")
ZARINPAL_SANDBOX = env.bool("ZARINPAL_SANDBOX", default=True)
DEFAULT_EXCHANGE_RATE_TON_IRR = env.int("DEFAULT_EXCHANGE_RATE_TON_IRR", default=0)
PLATFORM_SERVICE_FEE_PERCENT = env.int("PLATFORM_SERVICE_FEE_PERCENT", default=5)
GRAM_RATE_MARKUP_PERCENT = env.int("GRAM_RATE_MARKUP_PERCENT", default=0)

# Nobitex — Gram (Telegram TON) / RLS. Read-only public API.
NOBITEX_API_BASE_URL = env("NOBITEX_API_BASE_URL", default="https://apiv2.nobitex.ir")
NOBITEX_STATS_SRC_CURRENCY = env("NOBITEX_STATS_SRC_CURRENCY", default="gram")
NOBITEX_STATS_DST_CURRENCY = env("NOBITEX_STATS_DST_CURRENCY", default="rls")
NOBITEX_STATS_PAIR = env("NOBITEX_STATS_PAIR", default="gram-rls")
NOBITEX_ORDERBOOK_SYMBOL = env("NOBITEX_ORDERBOOK_SYMBOL", default="GRAMIRT")
NOBITEX_HTTP_TIMEOUT_SECONDS = env.float("NOBITEX_HTTP_TIMEOUT_SECONDS", default=12.0)
NOBITEX_HTTP_RETRIES = env.int("NOBITEX_HTTP_RETRIES", default=2)
NOBITEX_CACHE_TTL_SECONDS = env.int("NOBITEX_CACHE_TTL_SECONDS", default=90)
NOBITEX_MAX_RATE_AGE_SECONDS = env.int("NOBITEX_MAX_RATE_AGE_SECONDS", default=180)
NOBITEX_REFRESH_INTERVAL_SECONDS = env.int("NOBITEX_REFRESH_INTERVAL_SECONDS", default=60)
LIVE_STATS_MAX_AGE_SECONDS = env.int("LIVE_STATS_MAX_AGE_SECONDS", default=90)
QUOTE_VALIDITY_SECONDS = env.int("QUOTE_VALIDITY_SECONDS", default=300)
TON_PRICING_RISK_BUFFER_PERCENT = env.int("TON_PRICING_RISK_BUFFER_PERCENT", default=2)

# Product branding (override via env when brand is finalized)
PRODUCT_NAME = env("PRODUCT_NAME", default="گرام‌ادز")
# Preserve deployment overrides, but migrate the legacy public brand automatically.
if PRODUCT_NAME.strip() in {"تی‌ام‌ادز", "تی ام ادز", "TMADS", "tmads"}:
    PRODUCT_NAME = "گرام‌ادز"
PRODUCT_NAME_EN = "GramAds"
PRODUCT_TAGLINE = env(
    "PRODUCT_TAGLINE",
    default="تبلیغات تلگرام، ساده‌تر و هوشمندتر از همیشه",
)

# Security startup checks (no secret values logged)
def _missing_secrets() -> list[str]:
    missing = []
    if APP_ENV == "PRODUCTION" and SECRET_KEY.startswith("dev-"):
        missing.append("SECRET_KEY")
    if APP_ENV == "PRODUCTION" and not TELEGRAM_ADS_API_TOKEN:
        missing.append("TELEGRAM_ADS_API_TOKEN")
    if APP_ENV == "PRODUCTION" and TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED and len(TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY) < 32:
        missing.append("TELEGRAM_ADS_TOKEN_ENCRYPTION_KEY (32+ characters)")
    if APP_ENV == "PRODUCTION" and PAYMENT_GATEWAY == "fake":
        missing.append("PAYMENT_GATEWAY (production requires real gateway)")
    return missing


MISSING_PRODUCTION_SECRETS = _missing_secrets()
