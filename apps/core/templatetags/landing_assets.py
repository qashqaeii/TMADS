from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def landing_asset(name):
    """Use optimized artwork when built, with the master as a safe fallback."""
    stem = f"img/landing/{name}"
    optimized = f"{stem}.webp"
    return static(optimized if finders.find(optimized) else f"{stem}.png")
