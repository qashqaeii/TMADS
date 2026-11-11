from django.core.management.base import BaseCommand

from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.sync import sync_remote_advertisements_readonly


class Command(BaseCommand):
    help = "Read-only sync of linked Telegram Ads metadata"

    def handle(self, *args, **options):
        try:
            count = sync_remote_advertisements_readonly()
        except TelegramAdsError as exc:
            self.stderr.write(str(exc))
            return
        self.stdout.write(self.style.SUCCESS(f"Updated {count} linked advertisements"))
