"""Resolve Django settings module without silently loading local config in production."""
from __future__ import annotations

import os

LOCAL = "config.settings.local"
PRODUCTION = "config.settings.production"


def resolve_django_settings_module() -> str:
    """
    Prefer an explicit DJANGO_SETTINGS_MODULE.
    If APP_ENV=PRODUCTION, never fall back to local settings.
    Local/dev keeps the historical local default for manage.py DX.
    """
    explicit = (os.environ.get("DJANGO_SETTINGS_MODULE") or "").strip()
    app_env = (os.environ.get("APP_ENV") or "").strip().upper()
    if app_env == "PRODUCTION":
        if explicit in ("", LOCAL):
            return PRODUCTION
        return explicit
    return explicit or LOCAL


def apply_django_settings_module() -> str:
    module = resolve_django_settings_module()
    os.environ["DJANGO_SETTINGS_MODULE"] = module
    return module
