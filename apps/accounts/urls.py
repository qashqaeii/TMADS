from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from apps.telegram_ads.related_views import customer_related_account
from apps.telegram_ads.asset_views import customer_assets, customer_audience_update, customer_audience_delete, customer_pixel_event_manage

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("advertiser-account/", customer_related_account, name="related_account"),
    path("advertiser-assets/", customer_assets, name="advertiser_assets"),
    path("advertiser-assets/audiences/update/", customer_audience_update, name="audience_update"),
    path("advertiser-assets/audiences/delete/", customer_audience_delete, name="audience_delete"),
    path("advertiser-assets/pixel-events/manage/", customer_pixel_event_manage, name="pixel_event_manage"),
    path("profile/", views.profile_view, name="profile"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
]
