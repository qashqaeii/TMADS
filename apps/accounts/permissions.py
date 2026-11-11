from functools import wraps

from django.core.exceptions import PermissionDenied


def customer_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            raise PermissionDenied
        if user.role != user.Role.CUSTOMER and not user.is_superuser:
            raise PermissionDenied
        profile = getattr(user, "customer_profile", None)
        if profile is None:
            raise PermissionDenied
        if profile.is_suspended:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped


def staff_ops_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_platform_manager:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped
