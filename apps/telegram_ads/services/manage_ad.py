"""Audited, operator-mediated ad management; no financial balance mutations."""
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from apps.campaigns.models import Campaign, RemoteAdOperation, TelegramAdvertisement
from apps.core.models import AuditLog
from apps.finance.models import AdvertisingOrder
from apps.notifications.services import notify_customer
from apps.operations.review import require_recorded_approval
from apps.policies.services.preflight import CampaignPolicyPreflight, assert_submission_ready
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.services.account_connections import campaign_client
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.sync import has_financial_lock, _apply_remote_ad_payload, _sync_campaign_from_remote

Action = RemoteAdOperation.Action
Status = RemoteAdOperation.Status
OPEN = [Status.PENDING, Status.EXECUTING, Status.UNCERTAIN]


def parse_request(action, value="", *, currency="TON"):
    if action not in Action.values:
        raise ValueError("عملیات معتبر نیست.")
    precision = {"TON": 2, "EUR": 2, "XTR": 0}.get(str(currency or "TON").upper())
    if precision is None:
        raise ValueError("ارز حساب تبلیغاتی پشتیبانی نمی‌شود.")
    quantum = Decimal(1).scaleb(-precision)
    if action in (Action.INCREASE_BUDGET, Action.DECREASE_BUDGET):
        try:
            amount = Decimal(str(value))
            if not amount.is_finite() or not 0 < amount <= Decimal("100000000000") or amount != amount.quantize(quantum):
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"مبلغ باید مثبت و با دقت مجاز ارز {currency} باشد.") from None
        return {"amount": str(amount)}
    if action in (Action.EDIT_CPM, Action.EDIT_DAILY_LIMIT):
        try:
            amount = Decimal(str(value))
            if (not amount.is_finite() or not 0 <= amount <= Decimal("99999999.99")
                    or amount != amount.quantize(quantum)
                    or action == Action.EDIT_CPM and amount <= 0):
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"مبلغ باید معتبر و با دقت مجاز ارز {currency} باشد.") from None
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
    campaign = Campaign.objects.select_for_update().select_related("telegram_connection").get(pk=campaign_id, customer=customer)
    if has_financial_lock(campaign) or campaign.status in {Campaign.Status.CANCELLED, Campaign.Status.FAILED, Campaign.Status.DRAFT}:
        raise ValueError("ابتدا وضعیت ارسال و مالی کمپین باید مشخص شود.")
    ads = list(campaign.remote_ads.exclude(remote_ad_id="")[:2])
    if len(ads) != 1 or not ads[0].remote_ad_id.isdigit():
        raise ValueError("تبلیغ متصل یکتا یافت نشد.")
    ad = ads[0]
    if ad.operations.filter(status__in=OPEN).exists():
        raise ValueError("یک درخواست باز یا نیازمند تطبیق وجود دارد.")
    direct = bool(campaign.telegram_connection_id and campaign.telegram_connection.connection_type == "customer_owned")
    if action in (Action.INCREASE_BUDGET, Action.DECREASE_BUDGET) and not direct:
        raise ValueError("درخواست بودجه مدیریت‌شده باید از مسیر پیش‌فاکتور و بررسی اعتبار ثبت شود.")
    currency = campaign.telegram_connection.currency if direct else "TON"
    op = RemoteAdOperation.objects.create(
        advertisement=ad, action=action,
        request_payload=parse_request(action, value, currency=currency),
    )
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
        campaign = op.advertisement.campaign
        expected_currency = campaign.telegram_connection.currency if campaign.telegram_connection_id else "TON"
        if remote.get("currency") != expected_currency:
            raise ValueError("ارز تبلیغ با حساب متصل مطابقت ندارد.")
        return {k:float(v) for k,v in op.request_payload.items()}
    return op.request_payload


def operation_matches_remote(op, remote):
    """Match an uncertain write to a real read-only Ad record; never infer success."""
    if not isinstance(remote, dict):
        return False
    action = op.action
    if action in (Action.INCREASE_BUDGET, Action.DECREASE_BUDGET):
        try:
            before = Decimal(str(op.request_payload["before_remaining_budget"]))
            amount = Decimal(str(op.request_payload["amount"]))
            observed = Decimal(str(remote["remaining_budget"]))
            expected = before + amount if action == Action.INCREASE_BUDGET else before - amount
            campaign = op.advertisement.campaign
            currency = campaign.telegram_connection.currency
            return (
                remote.get("currency") == currency and before.is_finite()
                and amount.is_finite() and observed.is_finite() and expected >= 0
                and observed == expected
            )
        except (KeyError, InvalidOperation, TypeError, ValueError):
            return False
    if action == Action.REVIEW:
        return remote.get("status") in {"in_review", "active", "on_hold", "declined"}
    if action in (Action.PAUSE, Action.RESUME):
        state = str(remote.get("status") or "").lower()
        if action == Action.PAUSE:
            return remote.get("is_paused") is True or state in {"stopped", "on_hold"}
        return state == "active" and remote.get("is_paused") is not True
    if action in (Action.EDIT_CPM, Action.EDIT_DAILY_LIMIT):
        campaign = op.advertisement.campaign
        expected_currency = campaign.telegram_connection.currency if campaign.telegram_connection_id else "TON"
        if remote.get("currency") != expected_currency:
            return False
        field = "cpm" if action == Action.EDIT_CPM else "daily_budget_limit"
        try:
            observed = Decimal(str(remote[field]))
            expected = Decimal(str(op.request_payload[field]))
            return observed.is_finite() and expected.is_finite() and observed == expected
        except (KeyError, InvalidOperation, TypeError, ValueError):
            return False
    if action == Action.EDIT_TITLE:
        return isinstance(remote.get("title"), str) and remote["title"] == op.request_payload.get("title")
    return False


def reconcile_operation_readonly(operation_id, *, actor):
    """Confirm an uncertain operation using getAd only; no write or money movement.

    A mismatch, missing field or API error leaves the operation in uncertain
    state. Never retry the underlying mutation.
    """
    _manager(actor)
    op = RemoteAdOperation.objects.select_related("advertisement__campaign").get(pk=operation_id)
    if op.status != Status.UNCERTAIN:
        raise ValueError("فقط عملیات نیازمند تطبیق قابل بررسی است.")
    ad = op.advertisement
    if not ad.remote_ad_id.isdigit() or len(ad.remote_ad_id) > 20:
        raise ValueError("شناسه تبلیغ برای بررسی معتبر نیست.")
    remote = _checked_remote(campaign_client(ad.campaign), ad)
    if not operation_matches_remote(op, remote):
        raise ValueError("انجام عملیات در تلگرام تأیید نشد؛ وضعیت نامطمئن حفظ شد.")
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=ad.campaign_id)
        op = RemoteAdOperation.objects.select_for_update().get(pk=operation_id, advertisement=ad)
        if op.status != Status.UNCERTAIN:
            raise ValueError("وضعیت عملیات در حین بررسی تغییر کرد.")
        ad = TelegramAdvertisement.objects.select_for_update().get(pk=ad.pk)
        _apply_remote_ad_payload(ad, remote)
        ad.save(update_fields=["remote_status", "remote_status_raw", "placement", "promotion_url", "updated_at"])
        _sync_campaign_from_remote(ad)
        op.status = Status.COMPLETED
        op.note = "انجام عملیات از طریق استعلام خواندنی تلگرام تأیید شد."
        op.result_payload = {"ad_id": ad.remote_ad_id, "status": remote.get("status"), "confirmed": True, "reconciled_readonly": True}
        op.save(update_fields=["status", "note", "result_payload", "updated_at"])
        _audit(op, actor, "reconciled")
        notify_customer(campaign.customer, "نتیجه درخواست تبلیغ تأیید شد", op.get_action_display(), related_campaign_id=campaign.pk)
    return op



def _budget_transaction_evidence(client, op, ad):
    """Require a complete exact account↔ad transaction history for a budget write."""
    try:
        page = client.get_ad_transactions(ad.remote_ad_id, limit=100)
        rows = page.get("transactions")
        if not isinstance(rows, list) or page.get("next_offset") or page.get("total_count") != len(rows):
            return False
        amount = Decimal(str(op.request_payload["amount"]))
        expected = amount if op.action == Action.INCREASE_BUDGET else -amount
        matches = []
        for row in rows:
            peer = row.get("peer") or {}
            if peer.get("type") != "account":
                continue
            value = Decimal(str(row.get("amount")))
            timestamp = int(row.get("date"))
            if value == expected and timestamp >= int(op.created_at.timestamp()) - 5:
                matches.append(row)
        return len(matches) == 1
    except (KeyError, InvalidOperation, TypeError, ValueError, OverflowError):
        return False


def _customer_owned_guard(campaign, actor, op):
    profile = getattr(actor, "customer_profile", None)
    connection = campaign.telegram_connection
    if not profile or profile.is_suspended or profile.pk != campaign.customer_id:
        raise PermissionDenied
    if not connection or connection.connection_type != "customer_owned" or connection.status != "connected":
        raise ValueError("اتصال حساب شخصی برای این کمپین فعال نیست.")
    if not settings.TELEGRAM_ADS_WRITE_ENABLED or not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
        raise ValueError("عملیات زنده تبلیغات غیرفعال است.")
    if not getattr(settings, "TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED", False):
        raise ValueError("مدیریت مستقیم حساب مشتری در تنظیمات پلتفرم غیرفعال است.")
    if has_financial_lock(campaign) or campaign.status in {Campaign.Status.CANCELLED, Campaign.Status.FAILED, Campaign.Status.DRAFT}:
        raise ValueError("کمپین نیازمند تطبیق وضعیت است.")
    from apps.policies.constants import POLICY_SUMMARY_VERSION, TMADS_TERMS_VERSION
    from apps.policies.models import CampaignPolicyAcceptance
    from apps.policies.services.policy_versions import get_active_policy_version
    if not CampaignPolicyAcceptance.objects.filter(
        campaign=campaign, customer=campaign.customer,
        tmads_terms_version=TMADS_TERMS_VERSION,
        policy_summary_version=POLICY_SUMMARY_VERSION,
        policy_version=get_active_policy_version(),
    ).exists():
        raise ValueError("پذیرش شرایط و سیاست‌های جاری برای مدیریت تبلیغ ثبت نشده است.")
    if op.action in (Action.INCREASE_BUDGET, Action.DECREASE_BUDGET) and campaign.budget_currency != connection.currency:
        raise ValueError("ارز کمپین با حساب تلگرام یکسان نیست.")


def execute_customer_operation(operation_id, *, actor):
    """Execute with the customer's own token and never touch the TMADS wallet."""
    stub = RemoteAdOperation.objects.select_related(
        "advertisement__campaign__telegram_connection",
    ).get(pk=operation_id)
    ad = stub.advertisement
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().select_related("telegram_connection").get(pk=ad.campaign_id)
        op = RemoteAdOperation.objects.select_for_update().get(pk=operation_id)
        if op.status != Status.PENDING:
            raise ValueError("درخواست قبلاً اجرا شده یا نیازمند تطبیق است.")
        _customer_owned_guard(campaign, actor, op)
        if ad.operations.exclude(pk=op.pk).filter(status__in=OPEN).exists():
            raise ValueError("یک عملیات باز دیگر برای این تبلیغ وجود دارد.")
        client = campaign_client(campaign)
        remote = _checked_remote(client, ad)
        if op.action in (Action.INCREASE_BUDGET, Action.DECREASE_BUDGET):
            if remote.get("currency") != campaign.telegram_connection.currency:
                raise ValueError("ارز تبلیغ با حساب شخصی شما مطابقت ندارد.")
            if remote.get("status") not in {"stopped", "on_hold"}:
                raise ValueError("برای تغییر مستقیم بودجه، ابتدا تبلیغ را متوقف کنید.")
            amount = Decimal(str(op.request_payload["amount"]))
            before = Decimal(str(remote.get("remaining_budget")))
            if not before.is_finite() or before < 0:
                raise ValueError("مانده بودجه تبلیغ قابل تأیید نیست.")
            if op.action == Action.DECREASE_BUDGET and before < amount:
                raise ValueError("مانده بودجه تبلیغ برای کاهش انتخاب‌شده کافی نیست.")
            if op.action == Action.INCREASE_BUDGET:
                try:
                    available = Decimal(str(client.get_account().get("remaining_budget")))
                except (InvalidOperation, TypeError, ValueError):
                    raise ValueError("موجودی آزاد حساب تلگرام قابل تأیید نیست.") from None
                if not available.is_finite() or available < amount:
                    raise ValueError("موجودی آزاد حساب تلگرام برای افزایش بودجه کافی نیست.")
            op.request_payload = {
                **op.request_payload,
                "before_remaining_budget": str(before),
                "currency": campaign.telegram_connection.currency,
            }
        else:
            payload = _payload(op, remote)
        op.status = Status.EXECUTING
        op.save(update_fields=["status", "request_payload", "updated_at"])
        _audit(op, actor, "customer_claimed")

    try:
        if op.action == Action.REVIEW:
            client.submit_ad_for_review(ad.remote_ad_id)
        elif op.action == Action.INCREASE_BUDGET:
            client.increase_ad_budget(
                ad.remote_ad_id, float(op.request_payload["amount"]),
                idempotency_key=f"tmads-customer-ad-budget-{op.pk}",
            )
        elif op.action == Action.DECREASE_BUDGET:
            client.decrease_ad_budget(
                ad.remote_ad_id, float(op.request_payload["amount"]),
                idempotency_key=f"tmads-customer-ad-budget-{op.pk}",
            )
        else:
            client.edit_advertisement(ad.remote_ad_id, payload)
        confirmed = _checked_remote(client, ad)
        if not operation_matches_remote(op, confirmed):
            raise ValueError("تغییر در پاسخ خواندنی تلگرام تأیید نشد.")
        if op.action in (Action.INCREASE_BUDGET, Action.DECREASE_BUDGET):
            if not _budget_transaction_evidence(client, op, ad):
                raise ValueError("سند تراکنش تغییر بودجه کامل یا منطبق نیست.")
        with transaction.atomic():
            locked_campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
            op = RemoteAdOperation.objects.select_for_update().get(pk=op.pk)
            ad = TelegramAdvertisement.objects.select_for_update().get(pk=ad.pk)
            _apply_remote_ad_payload(ad, confirmed)
            ad.save(update_fields=["remote_status", "remote_status_raw", "placement", "promotion_url", "updated_at"])
            _sync_campaign_from_remote(ad)
            op.status = Status.COMPLETED
            op.result_payload = {
                "ad_id": ad.remote_ad_id, "status": confirmed.get("status"),
                "currency": confirmed.get("currency"), "remaining_budget": confirmed.get("remaining_budget"),
                "confirmed": True,
            }
            op.save(update_fields=["status", "result_payload", "updated_at"])
            _audit(op, actor, "customer_completed")
            notify_customer(locked_campaign.customer, "عملیات حساب تلگرام انجام شد",
                            op.get_action_display(), level="success", related_campaign_id=locked_campaign.pk)
        return op
    except Exception as exc:
        with transaction.atomic():
            op = RemoteAdOperation.objects.select_for_update().get(pk=op.pk)
            op.status = Status.UNCERTAIN
            op.note = "پاسخ عملیات قطعی نیست؛ تا تطبیق خواندنی دوباره اجرا نکنید."
            op.save(update_fields=["status", "note", "updated_at"])
            _audit(op, actor, "customer_uncertain")
        raise TelegramAdsError("نتیجه عملیات در حساب تلگرام نامطمئن است؛ درخواست را تکرار نکنید.") from exc


def reconcile_customer_operation_readonly(operation_id, *, actor):
    """Read-only reconciliation for an uncertain operation in the customer's account."""
    op = RemoteAdOperation.objects.select_related(
        "advertisement__campaign__telegram_connection",
    ).get(pk=operation_id)
    campaign = op.advertisement.campaign
    profile = getattr(actor, "customer_profile", None)
    if not profile or profile.pk != campaign.customer_id or op.status != Status.UNCERTAIN:
        raise PermissionDenied
    _customer_owned_guard(campaign, actor, op)
    ad = op.advertisement
    client = campaign_client(campaign)
    remote = _checked_remote(client, ad)
    if not operation_matches_remote(op, remote):
        raise ValueError("تغییر مورد انتظار در تبلیغ تأیید نشد؛ وضعیت نامطمئن حفظ شد.")
    if op.action in (Action.INCREASE_BUDGET, Action.DECREASE_BUDGET) and not _budget_transaction_evidence(client, op, ad):
        raise ValueError("سند تراکنش بودجه کامل نیست؛ وضعیت نامطمئن حفظ شد.")
    with transaction.atomic():
        campaign = Campaign.objects.select_for_update().get(pk=campaign.pk)
        op = RemoteAdOperation.objects.select_for_update().get(pk=operation_id)
        ad = TelegramAdvertisement.objects.select_for_update().get(pk=ad.pk)
        _apply_remote_ad_payload(ad, remote)
        ad.save(update_fields=["remote_status", "remote_status_raw", "placement", "promotion_url", "updated_at"])
        _sync_campaign_from_remote(ad)
        op.status = Status.COMPLETED
        op.note = "انجام عملیات با استعلام خواندنی و سند تراکنش تأیید شد."
        op.result_payload = {
            "ad_id": ad.remote_ad_id, "status": remote.get("status"),
            "remaining_budget": remote.get("remaining_budget"),
            "confirmed": True, "reconciled_readonly": True,
        }
        op.save(update_fields=["status", "note", "result_payload", "updated_at"])
        _audit(op, actor, "customer_reconciled")
        notify_customer(campaign.customer, "نتیجه عملیات تلگرام تأیید شد",
                        op.get_action_display(), level="success", related_campaign_id=campaign.pk)
    return op

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
        client = campaign_client(campaign)
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
        valid = operation_matches_remote(op, confirmed)
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
