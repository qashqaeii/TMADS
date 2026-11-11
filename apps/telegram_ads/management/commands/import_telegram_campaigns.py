from django.core.management.base import BaseCommand

from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.import_campaigns import (
    import_remote_campaigns_for_customer,
    prune_empty_draft_campaigns,
    resolve_import_customer,
)


class Command(BaseCommand):
    help = "Import Telegram Ads into local campaigns for superuser (central Hyper Tunnel account)."

    def add_arguments(self, parser):
        parser.add_argument("--username", help="Import owner (default: first superuser)")
        parser.add_argument(
            "--prune-drafts",
            action="store_true",
            help="Delete empty local drafts (کمپین جدید) without remote ad id",
        )
        parser.add_argument(
            "--no-stats",
            action="store_true",
            help="Skip per-ad statistics API calls after import",
        )

    def handle(self, *args, **options):
        try:
            customer = resolve_import_customer(username=options.get("username"))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return

        if options["prune_drafts"]:
            n = prune_empty_draft_campaigns(customer)
            self.stdout.write(self.style.WARNING(f"Removed {n} empty draft row(s)."))

        try:
            created, updated, skipped = import_remote_campaigns_for_customer(
                customer,
                fetch_statistics=not options["no_stats"],
            )
        except TelegramAdsError as exc:
            self.stderr.write(self.style.ERROR(f"Telegram Ads API: {exc}"))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Import done for {customer.user.username}: "
                f"created={created}, updated={updated}, skipped={skipped}"
            )
        )
