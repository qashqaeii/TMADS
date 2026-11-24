from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.telegram_bot.bot import get_bot, reset_bot_for_tests
from apps.telegram_bot.config import bot_token_configured, get_bot_config


class Command(BaseCommand):
    help = "ثبت یا حذف Webhook ربات GramAds در Telegram Bot API"

    def add_arguments(self, parser):
        parser.add_argument("--delete", action="store_true", help="حذف Webhook")
        parser.add_argument(
            "--url",
            type=str,
            default="",
            help="آدرس کامل Webhook (پیش‌فرض: PUBLIC_SITE_URL + مسیر تنظیمات)",
        )

    def handle(self, *args, **options):
        if not bot_token_configured():
            raise CommandError("GRAMADS_BOT_TOKEN تنظیم نشده است.")
        bot = get_bot()
        if not bot:
            raise CommandError("ربات آماده نشد.")
        secret = (getattr(settings, "GRAMADS_BOT_WEBHOOK_SECRET", "") or "").strip()
        if options["delete"]:
            bot.remove_webhook()
            self.stdout.write(self.style.SUCCESS("Webhook حذف شد."))
            return
        base = (settings.PUBLIC_SITE_URL or "").rstrip("/")
        if not base and not options["url"]:
            raise CommandError("PUBLIC_SITE_URL یا --url لازم است.")
        cfg = get_bot_config()
        webhook_url = options["url"] or f"{base}/{cfg.webhook_path.strip('/')}/"
        if not webhook_url.startswith("https://"):
            raise CommandError("Webhook باید HTTPS باشد.")
        bot.set_webhook(url=webhook_url, secret_token=secret or None, drop_pending_updates=True)
        self.stdout.write(self.style.SUCCESS(f"Webhook ثبت شد: {webhook_url}"))
        if secret:
            self.stdout.write("Secret Token از GRAMADS_BOT_WEBHOOK_SECRET استفاده می‌شود.")
        reset_bot_for_tests()