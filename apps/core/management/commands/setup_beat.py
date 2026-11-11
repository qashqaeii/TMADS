from django.core.management.base import BaseCommand
from django_celery_beat.models import IntervalSchedule, PeriodicTask


class Command(BaseCommand):
    help = "Register Celery beat periodic tasks in the database (optional; settings schedule also exists)."

    TASKS = (
        ("sync-active-ad-stats-hourly", "apps.telegram_ads.tasks.task_sync_active_ad_stats", 3600),
        ("sync-remote-ads-list-daily", "apps.telegram_ads.tasks.task_sync_remote_ads", 86400),
        ("refresh-ton-exchange-rate", "apps.finance.tasks.refresh_ton_exchange_rate", 60),
    )

    def handle(self, *args, **options):
        for name, task, every in self.TASKS:
            schedule, _ = IntervalSchedule.objects.get_or_create(
                every=every,
                period=IntervalSchedule.SECONDS,
            )
            PeriodicTask.objects.update_or_create(
                name=name,
                defaults={
                    "task": task,
                    "interval": schedule,
                    "enabled": True,
                },
            )
            self.stdout.write(self.style.SUCCESS(f"Periodic task ready: {name}"))
        self.stdout.write(self.style.SUCCESS("setup_beat done."))
