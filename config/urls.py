from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("health/", include("apps.core.urls")),
    path("", include("apps.public.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("app/", include("apps.dashboard.urls")),
    path("app/", include("apps.policies.urls")),
    path("campaigns/", include("apps.campaigns.urls")),
    path("finance/", include("apps.finance.urls")),
    path("support/", include("apps.support.urls")),
    path("ops/", include("apps.operations.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
