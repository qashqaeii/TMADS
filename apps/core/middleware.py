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
    """Bound failed sign-in attempts without blocking an entire shared-IP office.

    Identifiers are hashed in cache keys. Only trusted REMOTE_ADDR is used;
    untrusted forwarded IP headers cannot bypass these limits.
    """

    PATHS = {"/accounts/login/", "/accounts/register/", "/accounts/password-reset/"}
    WINDOW = 300
    LOGIN_IDENTITY_LIMIT = 10
    LOGIN_IP_LIMIT = 120
    OTHER_IP_LIMIT = 20

    def __init__(self, get_response):
        self.get_response = get_response

    def _key(self, label, value):
        from hashlib import sha256

        fingerprint = sha256(value.encode("utf-8", errors="replace")).hexdigest()[:32]
        return f"authlimit:{label}:{fingerprint}"

    def _increment(self, key):
        # Preserve the original fixed-window expiry instead of resetting the
        # clock after every attempt.
        cache.add(key, 0, timeout=self.WINDOW)
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, timeout=self.WINDOW)

    def __call__(self, request: HttpRequest):
        if settings.DEBUG and settings.APP_ENV == "LOCAL":
            return self.get_response(request)
        if request.method != "POST" or request.path not in self.PATHS:
            return self.get_response(request)

        from django.http import HttpResponse

        ip = request.META.get("REMOTE_ADDR") or "unknown"
        global_key = self._key(request.path, ip)
        is_login = request.path == "/accounts/login/"
        limit = self.LOGIN_IP_LIMIT if is_login else self.OTHER_IP_LIMIT
        identity = str(request.POST.get("username", "")).strip().casefold()[:150]
        identifier_key = self._key("login-identity", ip + ":" + identity)
        try:
            blocked = cache.get(global_key, 0) >= limit
            if is_login and cache.get(identifier_key, 0) >= self.LOGIN_IDENTITY_LIMIT:
                blocked = True
            if blocked:
                response = HttpResponse("درخواست‌های ورود بیش از حد مجاز است. چند دقیقه دیگر تلاش کنید.", status=429)
                response["Retry-After"] = str(self.WINDOW)
                response["Cache-Control"] = "no-store"
                return response
        except Exception:
            # An unavailable cache must not turn login into a platform outage.
            return self.get_response(request)

        response = self.get_response(request)
        try:
            if is_login:
                if request.user.is_authenticated:
                    cache.delete(identifier_key)
                else:
                    self._increment(global_key)
                    self._increment(identifier_key)
            else:
                self._increment(global_key)
        except Exception:
            pass
        return response
