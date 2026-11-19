"""Audited, operator-mediated ad management; no financial balance mutations."""
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.core.exceptions import PermissionDenied

from apps.campaigns.models import Campaign, RemoteAdOperation, TelegramAdvertisement
from apps.core.models import AuditLog
from apps.finance.models import AdvertisingOrder
from apps.notifications.services import notify_customer
from apps.operations.review import require_recorded_approval
from apps.policies.services.preflight import CampaignPolicyPreflight, assert_submission_ready
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.sync import has_financial_lock, _apply_remote_ad_payload, _sync_campaign_from_remote

Action = RemoteAdOperation.Action
Status = RemoteAdOperation.Status
OPEN = [Status.PENDING, Status.EXECUTING, Status.UNCERTAIN]


def parse_request(action, value=""):
    if action not in Action.values:
        raise ValueError("عملیات معتبر نیست.")
    if action in (Action.INCREASE_BUDGET,Action.DECREASE_BUDGET):
        raise ValueError("درخواست بودجه باید از مسیر پیش‌فاکتور و بررسی اعتبار ثبت شود.")
    if action in (Action.EDIT_CPM, Action.EDIT_DAILY_LIMIT):
        try:
            amount = Decimal(value)
            if (not amount.is_finite() or not 0 <= amount <= Decimal("99999999.99")
                    or amount != amount.quantize(Decimal(".01"))
                    or action == Action.EDIT_CPM and amount <= 0):
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("مبلغ TON باید معتبر و با حداکثر دو رقم اعشار باشد.") from None
        return {"cpm" if action == Action.EDIT_CPM else "daily_budget_limit": str(amount)}
    if action == Action.EDIT_TITLE:
        title = str(value).strip()
        if not title or len(title.encode("utf-8")) > 128:
            raise ValueError("عنوان داخلی باید بین ۱ تا ۱۲۸ بایت باشد.")
        return {"title": title}
    return {}


def _audit(op, actor, action):
    AuditLog.objects.create(actor=actor, action="remote_ad." + action, entity_type="remote_ad_operation",
        entity_id=op.pk, new_state={"campaign_id": str(op.advertisement.campaign_id), "action":op.action,"status":op.status})


@transaction.atomic
def request_operation(campaign_id, *, actor, action, value=""):
    customer = getattr(actor, "customer_profile", None)
    if not customer or customer.is_suspended:
        raise PermissionDenied
    campaign = Campaign.objects.select_for_update().get(pk=campaign_id, customer=customer)
    if has_financial_lock(campaign) or campaign.status in {Campaign.Status.CANCELLED, Campaign.Status.FAILED, Campaign.Status.DRAFT}:
        raise ValueError("ابتدا وضعیت ارسال و مالی کمپین باید مشخص شود.")
    ads = list(campaign.remote_ads.exclude(remote_ad_id="")[:2])
    if len(ads) != 1 or not ads[0].remote_ad_id.isdigit():
        raise ValueError("تبلیغ متصل یکتا یافت نشد.")
    ad = ads[0]
    if ad.operations.filter(status__in=OPEN).exists():
        raise ValueError("یک درخواست باز یا نیازمند تطبیق وجود دارد.")
    op = RemoteAdOperation.objects.create(advertisement=ad, action=action, request_payload=parse_request(action,value))
    _audit(op,actor,"requested")
    return op


def _manager(actor):
    if not actor.is_authenticated or not actor.is_platform_manager:
        raise PermissionDenied


@transaction.atomic
def reject_operation(operation_id, *, actor, reason):
    _manager(actor)
    op = RemoteAdOperation.objects.select_for_update().get(pk=operation_id)
    if op.status != Status.PENDING or not reason.strip():
        raise ValueError("فقط درخواست در انتظار با دلیل قابل رد است.")
    op.status=Status.REJECTED
    op.note=reason.strip()[:500]
    op.save(update_fields=["status","note","updated_at"])
    _audit(op,actor,"rejected")
    notify_customer(op.advertisement.campaign.customer,"درخواست تبلیغ رد شد",op.note,related_campaign_id=op.advertisement.campaign_id)
    return op


def _guard(campaign, op):
    if op.action in (Action.INCREASE_BUDGET,Action.DECREASE_BUDGET):
        raise ValueError("اجرای مالی تا تکمیل تسویه و تأیید شرایط تجاری غیرفعال است؛ هیچ مبلغی منتقل نمی‌شود.")
    if not settings.TELEGRAM_ADS_WRITE_ENABLED or not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
        raise ValueError("عملیات زنده تبلیغات غیرفعال است.")
    if not CampaignPolicyPreflight.operator_submission_allowed():
        raise ValueError("مجوز اپراتور تأیید نشده است.")
    if has_financial_lock(campaign) or campaign.status in {Campaign.Status.CANCELLED,Campaign.Status.FAILED,Campaign.Status.DRAFT}:
        raise ValueError("کمپین نیازمند تطبیق است.")
    if op.action != Action.PAUSE:
        if campaign.customer.is_suspended:
            raise ValueError("حساب مشتری غیرفعال است.")
        if not AdvertisingOrder.objects.filter(campaign_id=campaign.pk, customer=campaign.customer, status=AdvertisingOrder.Status.COMPLETED).exists():
            raise ValueError("برای این عملیات، سفارش تسویه‌شده و تأیید قبلی لازم است.")
        require_recorded_approval(campaign)
        assert_submission_ready(campaign)


def _checked_remote(client, ad):
    remote = client.get_ad(ad.remote_ad_id, return_target=True)
    if not isinstance(remote, dict) or str(remote.get("ad_id")) != ad.remote_ad_id:
        raise ValueError("هویت تبلیغ از تلگرام تأیید نشد.")
    return remote


def _payload(op, remote):
    action = op.action
    status = remote.get("status")
    if action in (Action.PAUSE, Action.RESUME):
        if status not in {"active","on_hold"}:
            raise ValueError("وضعیت فعلی تبلیغ امکان توقف یا ادامه را نمی‌دهد.")
        return {"is_paused": action == Action.PAUSE}
    if action == Action.REVIEW:
        if status != "ready_for_review":
            raise ValueError("تبلیغ در وضعیت آماده بررسی نیست.")
        return {}
    if action in (Action.EDIT_CPM, Action.EDIT_DAILY_LIMIT):
        if remote.get("currency") != "TON":
            raise ValueError("ویرایش مبلغ تنها برای حساب TON مجاز است.")
        return {k:float(v) for k,v in op.request_payload.items()}
    return op.request_payload


def execute_operation(operation_id, *, actor):
    """Claim before I/O; once a write is attempted, ambiguity blocks retries."""
    _manager(actor)
    stub = RemoteAdOperation.objects.select_related("advertisement").get(pk=operation_id)
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=stub.advertisement.campaign_id)
        op = RemoteAdOperation.objects.select_for_update().get(pk=operation_id)
        if op.status != Status.PENDING:
            raise ValueError("درخواست قبلاً بررسی شده است.")
        _guard(campaign,op)
        ad = op.advertisement
        client = TelegramAdsClient()
        remote = _checked_remote(client,ad)
        payload = _payload(op,remote)
        op.status=Status.EXECUTING
        op.save(update_fields=["status","updated_at"])
        _audit(op,actor,"claimed")
    try:
        if op.action == Action.REVIEW:
            client.submit_ad_for_review(ad.remote_ad_id)
        else:
            client.edit_advertisement(ad.remote_ad_id,payload)
        confirmed = _checked_remote(client,ad)
        if op.action == Action.REVIEW:
            valid=confirmed.get("status") in {"in_review","active","on_hold","declined"}
        elif op.action in (Action.PAUSE,Action.RESUME):
            paused = confirmed.get("is_paused") is True or confirmed.get("status") == "on_hold"
            valid = paused if op.action == Action.PAUSE else not paused and confirmed.get("status") == "active"
        elif op.action in (Action.EDIT_CPM,Action.EDIT_DAILY_LIMIT):
            field = next(iter(payload))
            valid = Decimal(str(confirmed.get(field, 0 if field == "daily_budget_limit" else None))) == Decimal(str(payload[field]))
        else:
            valid = confirmed.get("title") == payload.get("title")
        if not valid:
            raise ValueError("نتیجه عملیات هنوز تأیید نشده است.")
        with transaction.atomic():
            locked_campaign=Campaign.objects.select_for_update().get(pk=campaign.pk)
            op=RemoteAdOperation.objects.select_for_update().get(pk=op.pk)
            ad=TelegramAdvertisement.objects.select_for_update().get(pk=ad.pk)
            _apply_remote_ad_payload(ad,confirmed)
            ad.save(update_fields=["remote_status","remote_status_raw","placement","promotion_url","updated_at"])
            _sync_campaign_from_remote(ad)
            op.status=Status.COMPLETED
            op.result_payload={"ad_id":ad.remote_ad_id,"status":confirmed.get("status"),"confirmed":True}
            op.save(update_fields=["status","result_payload","updated_at"])
            _audit(op,actor,"completed")
            notify_customer(locked_campaign.customer,"عملیات تبلیغ تأیید شد",op.get_action_display(),related_campaign_id=locked_campaign.pk)
        return op
    except Exception as exc:
        with transaction.atomic():
            op=RemoteAdOperation.objects.select_for_update().get(pk=op.pk)
            op.status=Status.UNCERTAIN
            op.note="پاسخ قطعی دریافت نشد؛ اجرای دوباره تا تطبیق ممنوع است."
            op.save(update_fields=["status","note","updated_at"])
            _audit(op,actor,"uncertain")
        raise TelegramAdsError("نتیجه عملیات نیازمند تطبیق است. دوباره اجرا نکنید.") from exc


@transaction.atomic
def withdraw_operation(campaign_id, operation_id, *, actor):
    """Withdraw only an unexecuted request; never release live or reserved funds."""
    customer=getattr(actor,"customer_profile",None)
    if not customer or customer.is_suspended:
        raise PermissionDenied
    campaign=Campaign.objects.select_for_update().get(pk=campaign_id,customer=customer)
    op=RemoteAdOperation.objects.select_for_update().filter(pk=operation_id,advertisement__campaign=campaign).first()
    if not op or op.status!=Status.PENDING:
        raise ValueError("تنها درخواست در انتظار و متعلق به همین کمپین قابل انصراف است.")
    op.status=Status.REJECTED
    op.note="درخواست پیش از اجرا توسط مشتری پس گرفته شد."
    op.save(update_fields=["status","note","updated_at"])
    _audit(op,actor,"withdrawn")
    return op
