"""Upsert curated Similar Bots catalog entries (idempotent)."""

from django.core.management.base import BaseCommand

from apps.telegram_ads.catalog_seed import upsert_default_bot_catalog


class Command(BaseCommand):
    help = "Seed/refresh TargetBotCatalogEntry rows used by Similar Bots recommendations."

    def handle(self, *args, **options):
        stats = upsert_default_bot_catalog()
        self.stdout.write(
            self.style.SUCCESS(
                f"Bot catalog upserted: created={stats['created']} updated={stats['updated']} total={stats['total']}"
            )
        )
