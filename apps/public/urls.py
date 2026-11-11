from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("features/", views.features, name="features"),
    path("how-it-works/", views.how_it_works, name="how_it_works"),
    path("pricing/", views.pricing, name="pricing"),
    path("faq/", views.faq, name="faq"),
    path("contact/", views.contact, name="contact"),
    path("about/", views.about, name="about"),
    path("legal/terms/", views.terms, name="terms"),
    path("legal/privacy/", views.privacy, name="privacy"),
    path("legal/refund/", views.refund, name="refund"),
    path("legal/content-policy/", views.content_policy, name="content_policy"),
]
