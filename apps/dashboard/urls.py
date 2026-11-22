from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("live/gram-rate/", views.live_gram_rate, name="live_gram_rate"),
    path("notifications/", views.notifications, name="notifications"),
]
