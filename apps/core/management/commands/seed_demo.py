from django.core.management.base import BaseCommand

from apps.finance.models import ExchangeRate, PlatformFeeRule


class Command(BaseCommand):
    help = "Seed exchange rate and platform fee for local/demo."

    def handle(self, *args, **options):
        PlatformFeeRule.objects.get_or_create(is_active=True, defaults={"percent": 5})
        if not ExchangeRate.objects.filter(is_active=True).exists():
            ExchangeRate.objects.create(
                ton_per_irr=0,
                source="seed_demo",
                is_active=True,
                details={"irr_per_ton": 350_000_000},
            )
            self.stdout.write(self.style.SUCCESS("Exchange rate seeded (irr_per_ton=350_000_000)."))
        else:
            self.stdout.write("Active exchange rate already exists.")
        self.stdout.write(self.style.SUCCESS("seed_demo done."))
