"""Read-only diagnostic for official getTargetBot (no writes, no spend)."""

from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from apps.telegram_ads.exceptions import TelegramAdsNotConfigured
from apps.telegram_ads.services.bot_eligibility import check_bot_eligibility


class Command(BaseCommand):
    help = "Probe getTargetBot eligibility classification for one or more @usernames (read-only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "usernames",
            nargs="+",
            help="Bot usernames (@name, t.me/name, or bare name)",
        )
        parser.add_argument(
            "--no-cache",
            action="store_true",
            help="Bypass short-lived eligibility cache",
        )

    def handle(self, *args, **options):
        use_cache = not options["no_cache"]
        for raw in options["usernames"]:
            try:
                result = check_bot_eligibility(raw, use_cache=use_cache)
            except TelegramAdsNotConfigured as exc:
                raise CommandError(str(exc)) from exc
            except Exception as exc:
                raise CommandError(f"Internal error: {type(exc).__name__}") from exc
            safe = result.to_json()
            if safe.get("bot"):
                # Never log tokens; bot payload is public metadata only
                pass
            self.stdout.write(json.dumps(safe, ensure_ascii=False, indent=2))
