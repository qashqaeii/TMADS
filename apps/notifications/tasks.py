from celery import shared_task
from .sms import dispatch_pending


@shared_task
def dispatch_sms():
    return dispatch_pending()
