"""Workflow artwork with a safe fallback until the downloadable archive is installed."""
from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from .features_assets import feature_asset

register = template.Library()
FALLBACKS = {
    "hero": "features-hero",
    "signup": "feature-targeting",
    "campaign": "feature-campaign",
    "payment": "feature-wallet",
    "review": "feature-security",
    "publish": "feature-channels",
    "report": "feature-analytics",
    "target": "feature-targeting",
}


@register.simple_tag
def workflow_asset(role):
    if role not in FALLBACKS:
        return ""
    path = f"img/workflow/tmads_workflow_{role}.webp"
    if finders.find(path):
        return static(path)
    return feature_asset(FALLBACKS[role])
