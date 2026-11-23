"""Provision related accounts without moving funds or routing existing advertisements."""
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from django import forms
from apps.accounts.models import CustomerProfile
from apps.core.models import AuditLog
from apps.telegram_ads.models import RelatedAccountRequest
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.account_connections import ensure_platform_managed_connection
from apps.policies.services.preflight import CampaignPolicyPreflight

class RelatedAccountForm(forms.Form):
    title=forms.CharField(label="عنوان حساب",max_length=128)
    full_name=forms.CharField(label="نام کامل کسب‌وکار",max_length=256)
    email=forms.EmailField(label="ایمیل کسب‌وکار",max_length=64)
    phone_number=forms.RegexField(label="شماره تماس کسب‌وکار با کد کشور",regex=r"^\+[1-9][0-9]{6,14}$",max_length=16)
    country=forms.CharField(label="کشور",max_length=128)
    city=forms.CharField(label="شهر",max_length=128)
    legal_name=forms.CharField(label="نام حقوقی (اختیاری؛ ممکن است عمومی باشد)",max_length=256,required=False)
    consent=forms.BooleanField(label="اجازه انتقال مشخصات بالا به تلگرام برای ایجاد حساب را می‌دهم.")

def provisioning_enabled():
    return bool(settings.TELEGRAM_ADS_WRITE_ENABLED and settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED
                and getattr(settings,"TELEGRAM_ADS_RELATED_ACCOUNTS_ENABLED",False)
                and CampaignPolicyPreflight.operator_submission_allowed())

def audit(row,actor,verb):
    AuditLog.objects.create(actor=actor,action="related_account."+verb,entity_type="related_account",
        entity_id=row.pk,new_state={"status":row.status})

@transaction.atomic
def request_account(actor, data):
    profile=getattr(actor,"customer_profile",None)
    if not profile or profile.is_suspended:
        raise PermissionDenied
    form=RelatedAccountForm(data)
    if not form.is_valid():
        raise ValueError("اطلاعات حساب را کامل و معتبر وارد کنید.")
    CustomerProfile.objects.select_for_update().get(pk=profile.pk)
    row=RelatedAccountRequest.objects.filter(customer=profile).first()
    if row and row.status != RelatedAccountRequest.Status.REJECTED:
        raise ValueError("برای این مشتری قبلاً درخواست ثبت شده است.")
    values=dict(form.cleaned_data)
    values.pop("consent")
    title=values.pop("title")
    row,_=RelatedAccountRequest.objects.update_or_create(customer=profile,defaults={
        "title":title,"details":values,"consent_at":timezone.now(),"status":RelatedAccountRequest.Status.PENDING,
        "note":"","main_account_id":"","remote_account_id":"",
    })
    audit(row,actor,"requested")
    return row

def execute_account(row_id,actor):
    if not actor.is_platform_manager:
        raise PermissionDenied
    if not provisioning_enabled():
        raise ValueError("ایجاد حساب مرتبط در وضعیت فعلی مجاز نیست.")
    with transaction.atomic():
        row=RelatedAccountRequest.objects.select_for_update().get(pk=row_id)
        if row.status!=RelatedAccountRequest.Status.PENDING or row.customer.is_suspended:
            raise ValueError("درخواست آماده اجرا نیست.")
        client=TelegramAdsClient()
        main=client.get_account().get("account_id")
        if not isinstance(main,str) or not main or len(main)>256:
            raise ValueError("هویت حساب مرکزی قابل تأیید نیست.")
        row.main_account_id=main
        row.status=RelatedAccountRequest.Status.EXECUTING
        row.save(update_fields=["main_account_id","status","updated_at"])
        audit(row,actor,"claimed")
    try:
        result=client.create_related_account(title=row.title,details=row.details,idempotency_key="tmads-account-"+str(row.pk))
        remote=result.get("account_id")
        if not isinstance(remote,str) or not remote or len(remote)>256 or remote==main:
            raise ValueError
        checked=client.get_account_info(account_id=remote)
        if checked.get("account_id")!=remote or checked.get("title")!=row.title:
            raise ValueError
        with transaction.atomic():
            row=RelatedAccountRequest.objects.select_for_update().get(pk=row_id)
            row.remote_account_id=remote
            row.status=RelatedAccountRequest.Status.PROVISIONED
            row.details={}  # minimize retained company contact information
            row.save(update_fields=["remote_account_id","status","details","updated_at"])
            audit(row,actor,"provisioned")
        try:
            ensure_platform_managed_connection(row, actor=actor)
        except Exception as connection_exc:
            RelatedAccountRequest.objects.filter(pk=row_id).update(
                note="حساب تلگرام ایجاد شده؛ تأیید اتصال داخل TMADS نیازمند به‌روزرسانی است."
            )
            raise TelegramAdsError("حساب در تلگرام ایجاد شد؛ تأیید اتصال نیازمند بررسی مجدد است.") from connection_exc
        return row
    except Exception as exc:
        with transaction.atomic():
            row=RelatedAccountRequest.objects.select_for_update().get(pk=row_id)
            if row.status == RelatedAccountRequest.Status.PROVISIONED:
                row.note = row.note or "حساب ایجاد شده؛ اتصال نیازمند تطبیق است."
                row.save(update_fields=["note","updated_at"])
                audit(row,actor,"connection_uncertain")
            else:
                row.status=RelatedAccountRequest.Status.UNCERTAIN
                row.note="نتیجه ایجاد حساب نیازمند تطبیق است؛ اجرای مجدد مجاز نیست."
                row.save(update_fields=["status","note","updated_at"])
                audit(row,actor,"uncertain")
        if isinstance(exc, TelegramAdsError):
            raise
        raise TelegramAdsError("ایجاد حساب نیازمند تطبیق است؛ درخواست را دوباره اجرا نکنید.") from exc

@transaction.atomic
def reject_account(row_id, actor, note):
    if not actor.is_platform_manager:
        raise PermissionDenied
    row=RelatedAccountRequest.objects.select_for_update().get(pk=row_id)
    if row.status!=RelatedAccountRequest.Status.PENDING or not note.strip():
        raise ValueError("فقط درخواست در انتظار با دلیل قابل رد است.")
    row.status=RelatedAccountRequest.Status.REJECTED
    row.details={}
    row.note=note[:500]
    row.save(update_fields=["status","details","note","updated_at"])
    audit(row,actor,"rejected")
    return row
