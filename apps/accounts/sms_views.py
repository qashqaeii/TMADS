"""Authenticated phone enrollment; not a replacement for password authentication."""
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.crypto import salted_hmac, constant_time_compare
from django.views.decorators.cache import never_cache
from apps.accounts.models import CustomerProfile
from apps.accounts.permissions import customer_required
from apps.notifications.faraz import normalize_mobile, configured, send_pattern, DIGITS
from apps.notifications.models import SmsContact, SmsOtp, SmsPhoneThrottle


def digest(challenge, code):
    return salted_hmac("tmads.mobile.verify", f"{challenge.pk}:{challenge.customer_id}:{challenge.phone}:{code}",
                       algorithm="sha256").hexdigest()


def issue(customer, phone):
    if not phone or not configured("verify_mobile"):
        return "unavailable"
    now = timezone.now()
    with transaction.atomic():
        CustomerProfile.objects.select_for_update().get(pk=customer.pk)
        throttle, _ = SmsPhoneThrottle.objects.get_or_create(phone=phone)
        SmsPhoneThrottle.objects.select_for_update().get(pk=throttle.pk)
        recent = SmsOtp.objects.filter(created_at__gte=now-timedelta(hours=1))
        if (recent.filter(customer=customer).count() >= 5 or recent.filter(phone=phone).count() >= 5
                or recent.filter(customer=customer, created_at__gte=now-timedelta(seconds=60)).exists()
                or recent.filter(phone=phone, created_at__gte=now-timedelta(seconds=60)).exists()):
            return "rate"
        SmsOtp.objects.filter(customer=customer, consumed=False).update(consumed=True)
        code = f"{secrets.randbelow(1000000):06d}"
        challenge = SmsOtp(customer=customer, phone=phone, expires_at=now+timedelta(minutes=5))
        challenge.digest = digest(challenge, code)
        challenge.save()
    result = send_pattern(phone, "verify_mobile", {settings.FARAZSMS_OTP_ATTR: code})
    if result.state == "accepted":
        SmsOtp.objects.filter(pk=challenge.pk, consumed=False).update(accepted=True)
        return "sent"
    # Console never verifies real phone ownership.
    SmsOtp.objects.filter(pk=challenge.pk).update(consumed=True)
    return "unavailable"


def confirm(customer, raw):
    code = str(raw or "").strip().translate(DIGITS)
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return False
    with transaction.atomic():
        CustomerProfile.objects.select_for_update().get(pk=customer.pk)
        challenge = SmsOtp.objects.select_for_update().filter(customer=customer, consumed=False,
            accepted=True).order_by("-created_at").first()
        if not challenge:
            return False
        if challenge.expires_at <= timezone.now() or challenge.attempts >= 5:
            challenge.consumed = True
            challenge.save(update_fields=["consumed", "updated_at"])
            return False
        challenge.attempts += 1
        match = constant_time_compare(challenge.digest, digest(challenge, code))
        challenge.consumed = match or challenge.attempts >= 5
        challenge.save(update_fields=["attempts", "consumed", "updated_at"])
        if not match:
            return False
        try:
            with transaction.atomic():
                SmsContact.objects.update_or_create(customer=customer,
                    defaults={"phone": challenge.phone, "enabled": True})
                customer.user.mobile = challenge.phone
                customer.user.save(update_fields=["mobile"])
        except IntegrityError:
            return False
        return True


@never_cache
@login_required
@customer_required
def mobile_settings(request):
    customer = request.user.customer_profile
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "send":
            result = issue(customer, normalize_mobile(request.POST.get("phone")))
            if result == "sent":
                messages.success(request, "کد تأیید ارسال شد.")
            elif result == "rate":
                messages.error(request, "تعداد درخواست‌ها محدود است؛ کمی بعد تلاش کنید.")
            else:
                messages.error(request, "ارسال کد ممکن نیست؛ شماره و وضعیت سرویس را بررسی کنید.")
        elif action == "verify":
            if confirm(customer, request.POST.get("code")):
                messages.success(request, "شماره موبایل تأیید شد.")
            else:
                messages.error(request, "کد نامعتبر است یا امکان تأیید شماره وجود ندارد.")
        elif action == "disable":
            SmsContact.objects.filter(customer=customer).update(enabled=False)
        elif action == "enable":
            SmsContact.objects.filter(customer=customer).update(enabled=True)
        return redirect("accounts:mobile_settings")
    contact = SmsContact.objects.filter(customer=customer).first()
    challenge = SmsOtp.objects.filter(customer=customer, accepted=True, consumed=False,
        expires_at__gt=timezone.now()).order_by("-created_at").first()
    return render(request, "accounts/mobile_settings.html", {"contact": contact,
        "challenge": challenge, "sms_available": configured("verify_mobile") and settings.SMS_PROVIDER == "faraz"})
