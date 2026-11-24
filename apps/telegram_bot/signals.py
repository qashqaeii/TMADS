from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import Notification

from .config import bot_runtime_enabled
from .tasks import deliver_notification


@receiver(post_save, sender=Notification)
def notification_to_telegram(sender, instance: Notification, created: bool, **kwargs):
    if not created or not bot_runtime_enabled():
        return
    deliver_notification.delay(str(instance.pk))