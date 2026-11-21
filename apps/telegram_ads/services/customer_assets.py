"""Account-scoped resources. Only consented SHA256 digests are sent; no raw contacts stored."""
import uuid
import re
from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.models import RelatedAccountRequest, AccountAssetOperation
from apps.policies.services.preflight import CampaignPolicyPreflight

EVENT_TYPES=("page_view","add_to_cart","add_to_wishlist","customize_product","initiate_checkout","add_payment_info","purchase","contact","lead","schedule","complete_registration","submit_application","start_trial","subscribe","view_content","search","find_location","donate","custom")
SALT="tmads.customer-assets.v1"

def owned_account(actor):
    profile=getattr(actor,"customer_profile",None)
    if not profile or profile.is_suspended:
        raise PermissionDenied
    return RelatedAccountRequest.objects.filter(customer=profile,status="provisioned").exclude(remote_account_id="").first()

def verified_client(row):
    client=TelegramAdsClient()
    if (not row.main_account_id or row.main_account_id==row.remote_account_id
            or client.get_account().get("account_id")!=row.main_account_id
            or client.get_account_info(account_id=row.remote_account_id).get("account_id")!=row.remote_account_id):
        raise ValueError("هویت حساب اختصاصی قابل تأیید نیست.")
    return client

def enabled():
    return bool(settings.TELEGRAM_ADS_WRITE_ENABLED and settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED
        and getattr(settings,"TELEGRAM_ADS_CUSTOMER_ASSETS_ENABLED",False)
        and CampaignPolicyPreflight.operator_submission_allowed())

def issue_nonce(row):
    return signing.dumps({"account":str(row.pk),"operation":str(uuid.uuid4())},salt=SALT)

def create_asset(actor, data):
    row=owned_account(actor)
    if not row or not enabled():
        raise ValueError("ایجاد منابع در وضعیت فعلی مجاز نیست.")
    action=data.get("action")
    title=data.get("title","").strip()
    event_type=data.get("event_type","")
    if action not in {"audience","pixel","event"} or data.get("consent")!="on":
        raise ValueError("نوع منبع یا رضایت معتبر نیست.")
    if action!="pixel" and (not title or len(title)>64 or len(title.encode("utf-8"))>128):
        raise ValueError("عنوان منبع معتبر نیست.")
    if action=="event" and event_type not in EVENT_TYPES:
        raise ValueError("نوع رویداد معتبر نیست.")
    try:
        nonce=signing.loads(data.get("nonce",""),salt=SALT,max_age=900)
        operation_id=uuid.UUID(nonce["operation"])
        if nonce["account"]!=str(row.pk):
            raise ValueError
    except (signing.BadSignature,ValueError,KeyError,TypeError):
        raise ValueError("فرم منقضی یا نامعتبر است.") from None
    with transaction.atomic():
        row=RelatedAccountRequest.objects.select_for_update().get(pk=row.pk,customer=actor.customer_profile)
        if row.status!="provisioned" or row.customer.is_suspended:
            raise PermissionDenied
        if AccountAssetOperation.objects.filter(pk=operation_id).exists() or row.asset_operations.filter(state__in=["executing","uncertain"]).exists():
            raise ValueError("عملیات تکراری یا دارای نتیجه نامشخص است.")
        client=verified_client(row)
        op=AccountAssetOperation.objects.create(pk=operation_id,account=row,action=action)
    try:
        result=client.create_customer_asset(account_id=row.remote_account_id,action=action,title=title,
            event_type=event_type,operation_id=operation_id)
        field={"audience":"audience_id","pixel":"pixel_id","event":"event_id"}[action]
        ident=result.get(field)
        if isinstance(ident,bool) or not isinstance(ident,(str,int)) or not str(ident).strip() or len(str(ident))>256:
            raise ValueError("missing resource id")
        op.remote_id=str(ident)
        op.state="completed"
        op.save(update_fields=["remote_id","state","updated_at"])
        return op
    except Exception:
        AccountAssetOperation.objects.filter(pk=op.pk).update(state="uncertain")
        raise TelegramAdsError("نتیجه ایجاد منبع نامشخص است؛ تکرار نکنید و با پشتیبانی تماس بگیرید.") from None



def _sha256_list(raw):
    """Validate an explicitly pre-hashed set; never store or log input data."""
    if not isinstance(raw, str) or len(raw) > 650000:
        raise ValueError("فهرست هش‌ها بیش از حد مجاز است.")
    values = [part.strip().lower() for part in raw.splitlines() if part.strip()]
    if not 1 <= len(values) <= 10000 or len(values) != len(set(values)):
        raise ValueError("بین یک تا ده هزار هش یکتا وارد کنید.")
    if not all(re.fullmatch(r"[0-9a-f]{64}", value) for value in values):
        raise ValueError("هر سطر باید هش SHA-256 با ۶۴ کاراکتر هگزادسیمال باشد؛ شماره خام ارسال نکنید.")
    return values


def change_audience_contacts(actor, data):
    """A single durable account-scoped edit; unknown result blocks all retries.

    No plaintext phone number or hash is written to models, logs or AuditLog.
    This method does not automatically normalize/hash phone numbers because
    Telegram does not specify a universal normalization contract.
    """
    row = owned_account(actor)
    if not row or not enabled() or data.get("consent") != "on" or data.get("data_rights") != "on":
        raise ValueError("حساب اختصاصی، مجوز و رضایت استفاده از مخاطبان لازم است.")
    action = data.get("action")
    if action not in {"add", "remove"}:
        raise ValueError("نوع تغییر مخاطبان معتبر نیست.")
    try:
        audience_id = int(data.get("audience_id") or "")
    except (ValueError, TypeError):
        raise ValueError("شناسه مخاطبان معتبر نیست.") from None
    if not 0 < audience_id < 2147483648:
        raise ValueError("شناسه مخاطبان معتبر نیست.")
    hashes = _sha256_list(data.get("sha256_list"))
    try:
        nonce = signing.loads(data.get("nonce", ""), salt=SALT, max_age=900)
        operation_id = uuid.UUID(nonce["operation"])
        if nonce["account"] != str(row.pk):
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError, KeyError):
        raise ValueError("فرم منقضی یا نامعتبر است.") from None

    with transaction.atomic():
        row = RelatedAccountRequest.objects.select_for_update().get(pk=row.pk, customer=actor.customer_profile)
        if row.status != RelatedAccountRequest.Status.PROVISIONED or row.customer.is_suspended:
            raise PermissionDenied
        if (AccountAssetOperation.objects.filter(pk=operation_id).exists() or
                row.asset_operations.filter(state__in=["executing", "uncertain"]).exists()):
            raise ValueError("عملیات دیگری در جریان یا نیازمند تطبیق است.")
        client = verified_client(row)
        records = client.get_audiences_by_ids([audience_id], account_id=row.remote_account_id)
        if (not isinstance(records, list) or len(records) != 1
                or str(records[0].get("audience_id")) != str(audience_id)):
            raise ValueError("این گروه مخاطب در حساب اختصاصی شما تأیید نشد.")
        op = AccountAssetOperation.objects.create(
            pk=operation_id, account=row, action="audience_" + action,
            remote_id=str(audience_id),
        )

    try:
        result = client.edit_audience_hashes(
            account_id=row.remote_account_id, audience_id=audience_id,
            action=action, hashes=hashes,
        )
        if not isinstance(result, dict) or str(result.get("audience_id")) != str(audience_id):
            raise ValueError("شناسه گروه در پاسخ API مطابقت ندارد.")
        AccountAssetOperation.objects.filter(pk=op.pk).update(state="completed")
        return op
    except Exception:
        AccountAssetOperation.objects.filter(pk=op.pk).update(state="uncertain")
        raise TelegramAdsError("نتیجه تغییر مخاطبان نامشخص است؛ درخواست را تکرار نکنید.") from None



def delete_unused_audience(actor, data):
    """Remove only an unreferenced audience after verifying its account and ad count.

    Never accept a client-supplied ads_count. The claim is durable before any
    remote mutation; ambiguous outcomes never trigger an automatic retry.
    """
    row = owned_account(actor)
    if not row or not enabled() or data.get("consent") != "on":
        raise ValueError("مجوز مدیریت حساب و تأیید حذف لازم است.")
    try:
        audience_id = int(data.get("audience_id") or "")
        nonce = signing.loads(data.get("nonce", ""), salt=SALT, max_age=900)
        op_id = uuid.UUID(nonce["operation"])
        if nonce["account"] != str(row.pk) or not 0 < audience_id < 2147483648:
            raise ValueError
    except (ValueError, TypeError, KeyError, signing.BadSignature):
        raise ValueError("شناسه یا اعتبار فرم حذف نامعتبر است.") from None

    with transaction.atomic():
        row = RelatedAccountRequest.objects.select_for_update().get(pk=row.pk, customer=actor.customer_profile)
        if row.status != RelatedAccountRequest.Status.PROVISIONED or row.customer.is_suspended:
            raise PermissionDenied
        if (AccountAssetOperation.objects.filter(pk=op_id).exists() or
                row.asset_operations.filter(state__in=["executing", "uncertain"]).exists()):
            raise ValueError("یک عملیات قبلی در جریان است یا نیازمند تطبیق است.")
        client = verified_client(row)
        records = client.get_audiences_by_ids([audience_id], account_id=row.remote_account_id)
        if not isinstance(records, list) or len(records) != 1:
            raise ValueError("گروه متعلق به این حساب تأیید نشد.")
        source = records[0]
        if not isinstance(source, dict) or str(source.get("audience_id")) != str(audience_id):
            raise ValueError("شناسه گروه با حساب اختصاصی مطابقت ندارد.")
        # An absent ads_count is unknown, not zero.
        if type(source.get("ads_count")) is not int or source["ads_count"] != 0:
            raise ValueError("گروه مورد استفاده تبلیغات است یا تعداد تبلیغات آن تأیید نشده است.")
        operation = AccountAssetOperation.objects.create(
            pk=op_id, account=row, action="audience_delete", remote_id=str(audience_id),
        )

    try:
        if client.delete_unused_audience(account_id=row.remote_account_id, audience_id=audience_id) is not True:
            raise ValueError("حذف گروه از API تأیید نشد.")
        AccountAssetOperation.objects.filter(pk=operation.pk).update(state="completed")
        return operation
    except Exception:
        AccountAssetOperation.objects.filter(pk=operation.pk).update(state="uncertain")
        raise TelegramAdsError("نتیجه حذف گروه نامطمئن است؛ دوباره تلاش نکنید و درخواست بررسی دهید.") from None



def manage_pixel_event(actor, data):
    """Verify event identity in the user's account; prevent unsafe deletion.

    The new event title is never written to operation logs on an uncertain
    response, and the event is never silently recreated or deleted twice.
    """
    row = owned_account(actor)
    if not row or not enabled() or data.get("consent") != "on":
        raise ValueError("مجوز حساب و تأیید مدیریت رویداد لازم است.")
    action = data.get("action")
    if action not in {"rename", "delete"}:
        raise ValueError("اقدام رویداد معتبر نیست.")
    event_id = str(data.get("event_id") or "").strip()
    title = str(data.get("title") or "").strip()
    if not event_id or len(event_id) > 256 or any(ord(char) < 33 for char in event_id):
        raise ValueError("شناسه رویداد معتبر نیست.")
    if action == "rename" and (not 1 <= len(title.encode("utf-8")) <= 64):
        raise ValueError("عنوان رویداد باید بین ۱ تا ۶۴ بایت باشد.")
    try:
        nonce = signing.loads(data.get("nonce", ""), salt=SALT, max_age=900)
        operation_id = uuid.UUID(nonce["operation"])
        if nonce["account"] != str(row.pk):
            raise ValueError
    except (signing.BadSignature, ValueError, TypeError, KeyError):
        raise ValueError("فرم منقضی یا نامعتبر است.") from None

    with transaction.atomic():
        row = RelatedAccountRequest.objects.select_for_update().get(
            pk=row.pk, customer=actor.customer_profile)
        if row.status != RelatedAccountRequest.Status.PROVISIONED or row.customer.is_suspended:
            raise PermissionDenied
        if (AccountAssetOperation.objects.filter(pk=operation_id).exists() or
                row.asset_operations.filter(state__in=["executing", "uncertain"]).exists()):
            raise ValueError("یک عملیات دیگر در جریان یا نیازمند تطبیق است.")
        client = verified_client(row)
        events = client.get_pixel_events_by_ids([event_id], account_id=row.remote_account_id)
        if not isinstance(events, list) or len(events) != 1:
            raise ValueError("رویداد در حساب اختصاصی تأیید نشد.")
        event = events[0]
        # Telegram documents auto_created as optional and only True for
        # platform-created events. Missing means the event is not automatic.
        if (not isinstance(event, dict) or event.get("event_id") != event_id
                or event.get("auto_created", False) is not False):
            raise ValueError("ویرایش رویداد خودکار یا تأییدنشده مجاز نیست.")
        if action == "delete" and (type(event.get("ads_count")) is not int or event["ads_count"] != 0):
            raise ValueError("رویداد در تبلیغ استفاده می‌شود یا تعداد تبلیغات آن مشخص نیست.")
        operation = AccountAssetOperation.objects.create(
            pk=operation_id, account=row, action="event_" + action, remote_id=event_id,
        )
    try:
        outcome = client.change_pixel_event(
            account_id=row.remote_account_id, event_id=event_id, action=action,
            title=title if action == "rename" else None,
        )
        if action == "rename":
            verified = isinstance(outcome, dict) and outcome.get("event_id") == event_id and outcome.get("title") == title
        else:
            verified = outcome is True
        if not verified:
            raise ValueError("تغییر رویداد از API تأیید نشد.")
        AccountAssetOperation.objects.filter(pk=operation.pk).update(state="completed")
        return operation
    except Exception:
        AccountAssetOperation.objects.filter(pk=operation.pk).update(state="uncertain")
        raise TelegramAdsError("نتیجه تغییر رویداد نامطمئن است؛ عملیات را تکرار نکنید.") from None



def reset_unused_audience(actor, data):
    """Irreversible reset only for a verified unused custom audience.

    Does not accept user supplied audience counts; no contact data is logged.
    """
    row = owned_account(actor)
    if not row or not enabled() or data.get("consent") != "on" or data.get("confirm_text", "").strip() not in {"حذف کامل", "RESET"}:
        raise ValueError("برای تأیید، عبارت «حذف کامل» و مجوز حساب اختصاصی لازم است.")
    try:
        audience_id = int(data.get("audience_id") or "")
        nonce = signing.loads(data.get("nonce", ""), salt=SALT, max_age=900)
        operation_id = uuid.UUID(nonce["operation"])
        if nonce["account"] != str(row.pk) or not 0 < audience_id < 2147483648:
            raise ValueError
    except (ValueError, TypeError, KeyError, signing.BadSignature):
        raise ValueError("شناسه گروه یا اعتبار فرم معتبر نیست.") from None

    with transaction.atomic():
        row = RelatedAccountRequest.objects.select_for_update().get(pk=row.pk, customer=actor.customer_profile)
        if row.status != RelatedAccountRequest.Status.PROVISIONED or row.customer.is_suspended:
            raise PermissionDenied
        if (AccountAssetOperation.objects.filter(pk=operation_id).exists() or
                row.asset_operations.filter(state__in=["executing", "uncertain"]).exists()):
            raise ValueError("عملیات قبلی در جریان یا نیازمند تطبیق است.")
        client = verified_client(row)
        items = client.get_audiences_by_ids([audience_id], account_id=row.remote_account_id)
        if (not isinstance(items, list) or len(items) != 1 or
                not isinstance(items[0], dict) or str(items[0].get("audience_id")) != str(audience_id)
                or type(items[0].get("ads_count")) is not int
                or items[0]["ads_count"] != 0):
            raise ValueError("گروه قابل خالی‌سازی نیست؛ مالکیت یا نبود تبلیغ مرتبط تأیید نشد.")
        op = AccountAssetOperation.objects.create(
            pk=operation_id, account=row, action="audience_reset", remote_id=str(audience_id),
        )
    try:
        outcome = client.reset_unused_audience(
            account_id=row.remote_account_id, audience_id=audience_id,
        )
        if not isinstance(outcome, dict) or str(outcome.get("audience_id")) != str(audience_id):
            raise ValueError("نتیجه خالی‌سازی از API تأیید نشد.")
        AccountAssetOperation.objects.filter(pk=op.pk).update(state="completed")
        return op
    except Exception:
        AccountAssetOperation.objects.filter(pk=op.pk).update(state="uncertain")
        raise TelegramAdsError("نتیجه خالی‌سازی نامطمئن است؛ درخواست را تکرار نکنید.") from None
