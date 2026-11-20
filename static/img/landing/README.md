# TMADS landing art

The ten original uploaded images are preserved as descriptive PNG masters.
`python scripts/optimize_landing_assets.py` builds WebP derivatives (max 1600 px for hero background, 1200 px for hero artwork, 360 px for card images).
The standard `python manage.py runserver` and `python manage.py collectstatic` commands build them automatically; no online service is used. Generated WebP files are not committed. Templates fall back to the masters for test or alternate development entry points.

Artwork is illustrative, not actual dashboard data. Marketing text stays in HTML.
