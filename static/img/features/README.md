# TMADS Features — transparent Orbit artwork

The ten descriptive-named WebP masters are the transparent illustrations.
The original three background images remain intentionally opaque.
The public template resolves each semantic role via TRANSPARENT_ART in
scripts/optimize_features_assets.py; the announcements role reuses the
broadcast illustration. The existing earlier art is retained as a fallback.

Run `python scripts/optimize_features_assets.py` or the usual
`python manage.py runserver` / `python manage.py collectstatic` to generate
lightweight .optimized.webp files (1200px hero, 480px icons, real alpha).
Masters stay unchanged; generated derivatives are ignored by Git.
