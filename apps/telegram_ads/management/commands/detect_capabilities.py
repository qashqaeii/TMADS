from django.core.management.base import BaseCommand

from apps.campaigns.models import TelegramAdvertisement
from apps.telegram_ads.exceptions import TelegramAdsNotConfigured
from apps.telegram_ads.services.capabilities import refresh_api_capabilities


class Command(BaseCommand):
    help = "Probe Telegram Ads API (read methods per official docs) and store capability states"

    def handle(self, *args, **options):
        sample = (
            TelegramAdvertisement.objects.exclude(remote_ad_id="")
            .order_by("-updated_at")
            .values_list("remote_ad_id", flat=True)
            .first()
        )
        sample_ad_id = int(sample) if sample and str(sample).isdigit() else None
        try:
            n = refresh_api_capabilities(sample_ad_id=sample_ad_id)
        except TelegramAdsNotConfigured as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return
        self.stdout.write(self.style.SUCCESS(f"capabilities refreshed: {n} rows"))
