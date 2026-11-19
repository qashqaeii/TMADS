from django.urls import path

from . import views, remote_views

app_name = "campaigns"

urlpatterns = [
    path("", views.campaign_list, name="list"),
    path("refresh-stats/", views.campaign_refresh_stats, name="refresh_stats"),
    path("new/", views.campaign_wizard, name="wizard_new"),
    path("<uuid:campaign_id>/", views.campaign_detail, name="detail"),
    path("<uuid:campaign_id>/manage/", remote_views.remote_management, name="remote_management"),
    path("<uuid:campaign_id>/wizard/", views.campaign_wizard, name="wizard"),
    path("<uuid:campaign_id>/delete/", views.campaign_delete, name="delete"),
    path("<uuid:campaign_id>/duplicate/", views.campaign_duplicate, name="duplicate"),
    path("<uuid:campaign_id>/creative/<uuid:creative_id>/media/", views.creative_media_download, name="creative_media"),
    path("<uuid:campaign_id>/autosave/", views.campaign_autosave, name="autosave"),
    path("<uuid:campaign_id>/policy-preview/", views.campaign_policy_preview, name="policy_preview"),
    path("studio/catalog/countries/", views.studio_catalog_countries, name="catalog_countries"),
    path("studio/catalog/languages/", views.studio_catalog_languages, name="catalog_languages"),
    path("studio/catalog/topics/", views.studio_catalog_topics, name="catalog_topics"),
    path("studio/catalog/locations/", views.studio_catalog_locations, name="catalog_locations"),
    path("studio/catalog/resolve-bot/", views.studio_catalog_resolve_bot, name="catalog_resolve_bot"),
    path("studio/catalog/resolve-channel/", views.studio_catalog_resolve_channel, name="catalog_resolve_channel"),
    path("<uuid:campaign_id>/export.csv", views.campaign_export_csv, name="export_csv"),
]
