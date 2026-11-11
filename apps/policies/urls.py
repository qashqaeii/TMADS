from django.urls import path

from . import views

app_name = "policies"

urlpatterns = [
    path("ad-policies/", views.ad_policies, name="ad_policies"),
]
