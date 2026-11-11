from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponseForbidden


class CustomerContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        request.customer_profile = None
        user = getattr(request, "user", None)
        if user and user.is_authenticated and hasattr(user, "customer_profile"):
            request.customer_profile = user.customer_profile
        return self.get_response(request)


class AuthRateLimitMiddleware:
    """Light rate limit on login/register POST."""

    PATHS = {"/accounts/login/", "/accounts/register/", "/accounts/password-reset/"}
    LIMIT = 20
    WINDOW = 300

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if settings.DEBUG and settings.APP_ENV == "LOCAL":
            return self.get_response(request)
        if request.method == "POST" and request.path in self.PATHS:
            ip = request.META.get("REMOTE_ADDR", "unknown")
            key = f"ratelimit:{request.path}:{ip}"
            count = cache.get(key, 0)
            if count >= self.LIMIT:
                return HttpResponseForbidden("درخواست زیاد است. کمی بعد تلاش کنید.")
            cache.set(key, count + 1, self.WINDOW)
        return self.get_response(request)
