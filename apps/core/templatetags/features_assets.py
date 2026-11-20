"""Feature artwork: use downloaded WebP files, or the existing Orbit artwork."""
from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

from .landing_assets import landing_asset

register = template.Library()

FEATURE_ART = {
    "features-hero": "telegram-banner",
    "features-bg-wave": "hero-background",
    "feature-campaign": "channels",
    "feature-targeting": "users-targeting",
    "feature-channels": "channels",
    "feature-bots": "bots-miniapps",
    "feature-analytics": "analytics-budget",
    "feature-wallet": "analytics-budget",
    "feature-security": "order-review",
    "feature-control": "order-review",
    "feature-performance": "analytics-budget",
    "feature-support": "channels",
    "features-globe": "orbit-dark",
    "features-shapes": "orbit-dark",
}


@register.simple_tag
def feature_asset(name):
    fallback = FEATURE_ART[name]
    path = f"img/features/{name}.webp"
    return static(path) if finders.find(path) else landing_asset(fallback)
