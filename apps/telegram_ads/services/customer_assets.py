"""Account-scoped resources. No contact lists stored or uploaded in this phase."""
import uuid
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
