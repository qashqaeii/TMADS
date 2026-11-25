from __future__ import annotations

import json
import logging

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.notifications.models import Notification

from ..bot import get_bot
from ..formatters import escape_html, named_site_url
from ..models import TelegramNotificationPreference, TelegramOutbox, TelegramUserLink
logger = logging.getLogger(__name__)


def _should_notify(link: TelegramUserLink, notification: Notification) -> bool:
    try:
        prefs = link.notification_prefs
    except TelegramNotificationPreference.DoesNotExist:
        return True
    title = (notification.title or "").lower()
    if "کیف پول" in title or "پرداخت" in title or "شارژ" in title:
        return prefs.payment_events
    if "بودجه" in title or "budget" in title:
        return prefs.budget_alerts
    if "کمپین" in title or "تبلیغ" in title:
        return prefs.campaign_status
    if "پشتیبانی" in title or "تیکت" in title:
        return prefs.support_replies
    return True


@transaction.atomic
def enqueue_notification_for_customer(notification: Notification) -> int:
    dedupe = f"notif:{notification.pk}"
    links = TelegramUserLink.objects.filter(customer=notification.customer, is_active=True)
    created = 0
    for link in links:
        if not _should_notify(link, notification):
            continue
        body = f"🔔 <b>{escape_html(notification.title)}</b>"
        if notification.body:
            body += f"\n{escape_html(notification.body)}"
        markup = {}
        detail_url = None
        if notification.related_campaign_id:
            detail_url = named_site_url("campaigns:detail", notification.related_campaign_id)
        elif settings.PUBLIC_SITE_URL:
            detail_url = named_site_url("dashboard:home")
        if detail_url:
            markup = {"inline_keyboard": [[{"text": "مشاهده جزئیات", "url": detail_url}]]}
        _, was_created = TelegramOutbox.objects.get_or_create(
            dedupe_key=f"{dedupe}:{link.pk}",
            defaults={
                "link": link,
                "telegram_user_id": link.telegram_user_id,
                "chat_id": link.chat_id,
                "body": body,
                "reply_markup": markup,
                "notification_id": notification.pk,
            },
        )
        if was_created:
            created += 1
    return created


MAX_OUTBOX_ATTEMPTS = 8
STUCK_SENDING_MINUTES = 5


def recover_stuck_outbox_rows() -> int:
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(minutes=STUCK_SENDING_MINUTES)
    qs = TelegramOutbox.objects.filter(
        status=TelegramOutbox.Status.SENDING,
        updated_at__lt=cutoff,
        attempt_count__lt=MAX_OUTBOX_ATTEMPTS,
    )
    return qs.update(status=TelegramOutbox.Status.QUEUED, last_error="stuck_sending_recovered")


def send_outbox_row(row: TelegramOutbox) -> bool:
    """Claim before sending; parallel Beat/worker runs may not send the same row."""
    bot = get_bot()
    if not bot:
        return False
    claimed = TelegramOutbox.objects.filter(
        pk=row.pk,
        status__in=[TelegramOutbox.Status.QUEUED, TelegramOutbox.Status.FAILED],
        attempt_count__lt=MAX_OUTBOX_ATTEMPTS,
    ).update(
        status=TelegramOutbox.Status.SENDING,
        attempt_count=F("attempt_count") + 1,
        updated_at=timezone.now(),
    )
    if not claimed:
        return False
    row.refresh_from_db()
    # A timeout after a successful external send can remain ambiguous; this is
    # best-effort at-least-once delivery, not an exactly-once Telegram guarantee.
    try:
        kwargs = {}
        if row.reply_markup:
            kwargs["reply_markup"] = json.dumps(row.reply_markup)
        bot.send_message(row.chat_id, row.body, parse_mode="HTML", **kwargs)
        TelegramOutbox.objects.filter(pk=row.pk, status=TelegramOutbox.Status.SENDING).update(
            status=TelegramOutbox.Status.SENT, sent_at=timezone.now(),
            last_error="", updated_at=timezone.now(),
        )
        row.status = TelegramOutbox.Status.SENT
        return True
    except Exception as exc:
        err = str(exc)[:500]
        TelegramOutbox.objects.filter(pk=row.pk, status=TelegramOutbox.Status.SENDING).update(
            status=TelegramOutbox.Status.FAILED, last_error=err, updated_at=timezone.now(),
        )
        if "blocked" in err.lower() or "deactivate" in err.lower():
            if row.link_id:
                from .link import revoke_link
                revoke_link(row.link, reason="ربات توسط کاربر مسدود شد")
        logger.warning("telegram outbox failed: %s", err)
        return False
