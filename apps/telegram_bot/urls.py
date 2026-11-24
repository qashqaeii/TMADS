from django.urls import path

from . import link_views, webhook

app_name = "telegram_bot"

urlpatterns = [
    path("webhook/", webhook.telegram_webhook, name="webhook"),
    path("link-token/", link_views.create_link_token_view, name="create_link_token"),
]