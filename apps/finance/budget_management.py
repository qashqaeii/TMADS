"""Budget change proposals, not payments. No wallet or Telegram writes."""
from decimal import Decimal, InvalidOperation
from django.core import signing
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils.crypto import salted_hmac
from apps.campaigns.models import Campaign, RemoteAdOperation
from apps.finance.services.campaign_pricing import build_campaign_quote, quote_expired
from apps.telegram_ads.services.manage_ad import OPEN, _audit
from apps.telegram_ads.services.sync import has_financial_lock

SALT = "tmads.budget-proposal.v1"

def _eligible(campaign, actor):
    customer=getattr(actor,"customer_profile",None)
    if not customer or customer.is_suspended or customer.pk != campaign.customer_id:
        raise PermissionDenied
    if has_financial_lock(campaign) or campaign.status in {Campaign.Status.DRAFT,Campaign.Status.CANCELLED,Campaign.Status.FAILED}:
        raise ValueError("کمپین نیازمند بررسی وضعیت مالی است.")
    ads=list(campaign.remote_ads.exclude(remote_ad_id="")[:2])
    if len(ads)!=1:
        raise ValueError("تبلیغ متصل یکتا یافت نشد.")
    ad=ads[0]
    if ad.remote_status_raw.get("currency") != "TON":
        raise ValueError("ارز حساب تبلیغ هنوز تأیید نشده یا TON نیست.")
    if ad.operations.filter(status__in=OPEN).exists():
        raise ValueError("یک درخواست باز برای این تبلیغ وجود دارد.")
    return ad

def _amount(value, *, money=False):
    try:
        d=Decimal(str(value))
        precision=Decimal("1") if money else Decimal(".01")
        if not d.is_finite() or not 0 < d <= Decimal("100000000000") or d != d.quantize(precision):
            raise ValueError
        return d
    except (InvalidOperation,ValueError,TypeError):
        raise ValueError("مبلغ نامعتبر است.") from None

def preview_budget(campaign, *, actor, action, value):
    ad=_eligible(campaign,actor)
    if action=="increase_budget":
        toman=int(_amount(value,money=True))
        if toman<100000:
            raise ValueError("حداقل بودجه پیشنهادی ۱۰۰ هزار تومان است.")
        quote=build_campaign_quote(toman*10)
        data={"quote":quote,"requested_toman":toman,"amount_ton":quote["ton_allocation"]}
    elif action=="decrease_budget":
        amount=_amount(value)
        remaining=_amount(ad.remote_status_raw.get("remaining_budget"))
        if amount>remaining:
            raise ValueError("مقدار درخواستی بیشتر از مانده گزارش‌شده تبلیغ است.")
        data={"amount_ton":str(amount)}
    else:
        raise ValueError("نوع درخواست معتبر نیست.")
    data.update({"action":action,"campaign_id":str(campaign.pk),"ad_id":str(ad.pk),"customer_id":str(campaign.customer_id)})
    return data, signing.dumps(data,salt=SALT,compress=True)

@transaction.atomic
def submit_budget_proposal(campaign_id, *, actor, token):
    campaign=Campaign.objects.select_for_update().get(pk=campaign_id)
    ad=_eligible(campaign,actor)
    try:
        data=signing.loads(token,salt=SALT,max_age=300)
    except signing.BadSignature:
        raise ValueError("پیش‌نمایش منقضی یا نامعتبر است.") from None
    if data.get("campaign_id")!=str(campaign.pk) or data.get("ad_id")!=str(ad.pk) or data.get("customer_id")!=str(campaign.customer_id):
        raise ValueError("پیش‌نمایش با این تبلیغ مطابقت ندارد.")
    action=data.get("action")
    if action not in {"increase_budget","decrease_budget"}:
        raise ValueError("نوع درخواست معتبر نیست.")
    if action=="increase_budget" and quote_expired(data.get("quote",{})):
        raise ValueError("اعتبار پیش‌فاکتور به پایان رسیده است.")
    fingerprint=salted_hmac(SALT,token).hexdigest()
    if ad.operations.filter(request_payload__proposal_key=fingerprint).exists():
        raise ValueError("این پیش‌نمایش قبلاً ثبت شده است.")
    op=RemoteAdOperation.objects.create(advertisement=ad,action=action,
        request_payload={**data,"proposal_key":fingerprint},
        note="درخواست بررسی مالی؛ هنوز هیچ مبلغی برداشت یا منتقل نشده است.")
    _audit(op,actor,"budget_proposed")
    return op
