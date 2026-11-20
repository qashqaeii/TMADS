from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = f"مدیریت {settings.PRODUCT_NAME}"
admin.site.site_title = settings.PRODUCT_NAME
admin.site.index_title = "مدیریت سامانه"

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

# Uploaded creative media is served only through an authenticated ownership-checked view.
