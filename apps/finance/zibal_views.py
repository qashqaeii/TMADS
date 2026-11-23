"""Zibal checkout, callback and customer-only receipt; never trust callback as payment proof."""
import uuid
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from apps.accounts.permissions import customer_required
from apps.public.seo import public_origin
from .gateways import get_payment_gateway
from .gateways.zibal import START, track_id
from .models import Payment, PaymentVerification
from .services import complete_topup_payment


def callback_url(request, payment_id):
    path = reverse("finance:zibal_callback", kwargs={"payment_id": payment_id})
    if settings.APP_ENV.upper() == "PRODUCTION":
        origin = public_origin()
        return origin + path if origin else ""
    return request.build_absolute_uri(path)


def initiate_zibal(request, amount_irr):
    # A repeated submit of the same form never starts a second provider transaction.
    try:
        nonce = uuid.UUID(request.POST.get("payment_nonce", ""))
    except (ValueError, TypeError, AttributeError):
        messages.error(request, "فرم پرداخت منقضی شده است؛ دوباره مبلغ را انتخاب کنید.")
        return redirect("finance:topup")
    customer = request.user.customer_profile
    payment, created = Payment.objects.get_or_create(
        idempotency_key=f"zibal-{customer.pk}-{nonce}",
        defaults={"customer": customer, "amount_irr": amount_irr, "gateway": "zibal",
                  "provider_amount_irr": amount_irr},
    )
    if payment.customer_id != customer.pk or payment.gateway != "zibal" or payment.amount_irr != amount_irr:
        messages.error(request, "مبلغ یا درخواست پرداخت معتبر نیست.")
        return redirect("finance:topup")
    if not created:
        if payment.status == Payment.Status.REDIRECTED and payment.provider_reference:
            return redirect("finance:payment_start", payment_id=payment.pk)
        return redirect("finance:payment_result", payment_id=payment.pk)
    url = callback_url(request, payment.pk)
    gateway = get_payment_gateway("zibal")
    result = gateway.create_payment(amount_irr=amount_irr, callback_url=url,
                                    description=f"topup-{payment.pk}") if url else None
    ref = track_id(result.provider_reference) if result and result.success else ""
    if not ref:
        # No redirect was issued; there was no customer handoff to this attempt.
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        return redirect("finance:payment_result", payment_id=payment.pk)
    try:
        with transaction.atomic():
            payment.provider_reference = ref
            payment.status = Payment.Status.REDIRECTED
            payment.save(update_fields=["provider_reference", "status", "updated_at"])
    except IntegrityError:
        Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.FAILED)
        return redirect("finance:payment_result", payment_id=payment.pk)
    return redirect("finance:payment_start", payment_id=payment.pk)


def owned_payment(request, payment_id):
    return get_object_or_404(Payment, pk=payment_id, customer=request.user.customer_profile,
                             gateway="zibal", order__isnull=True)


@never_cache
@login_required
@customer_required
@require_GET
def payment_start(request, payment_id):
    payment = owned_payment(request, payment_id)
    ref = track_id(payment.provider_reference)
    if payment.status != Payment.Status.REDIRECTED or not ref:
        return redirect("finance:payment_result", payment_id=payment.pk)
    return render(request, "finance/payment_start.html", {
        "payment": payment, "gateway_url": START + ref,
    })


def verify_zibal(payment_id, *, expected_track):
    """Verify Zibal outside a long-held row lock; finalize under a short atomic section."""
    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(
            pk=payment_id, gateway="zibal", order__isnull=True
        ).first()
        if not payment or not expected_track or payment.provider_reference != expected_track:
            return
        if payment.status != Payment.Status.REDIRECTED or payment.provider_amount_irr != payment.amount_irr:
            return
        latest = payment.verifications.order_by("-created_at").first()
        if latest and (timezone.now() - latest.created_at).total_seconds() < 10:
            return
        amount_irr = payment.amount_irr

    result = get_payment_gateway("zibal").verify_payment(
        provider_reference=expected_track, amount_irr=amount_irr
    )
    audit = result.raw or {}
    matches = (
        result.success
        and result.provider_reference == expected_track
        and type(audit.get("paid_amount_irr")) is int
        and audit.get("paid_amount_irr") == amount_irr
        and bool(audit.get("bank_reference"))
    )

    with transaction.atomic():
        payment = Payment.objects.select_for_update().filter(
            pk=payment_id, gateway="zibal", order__isnull=True
        ).first()
        if not payment or payment.status != Payment.Status.REDIRECTED:
            return
        PaymentVerification.objects.create(
            payment=payment,
            success=bool(matches),
            raw_payload={
                "code": audit.get("code"),
                "paid_amount_irr": audit.get("paid_amount_irr"),
                "bank_reference": audit.get("bank_reference", ""),
                "error": audit.get("error", ""),
            },
        )
        if matches:
            complete_topup_payment(payment, deposit_description="شارژ کیف پول (زیبال)")
    # A definitive unpaid result is not proof of cancellation forever. Keep the
    # original attempt available for safe rechecking; do not encourage a new charge.


@never_cache
@require_GET
def zibal_callback(request, payment_id):
    # Browser may have lost its login session. Only a matching stored track ID may
    # trigger authenticated server-to-server verification. Receipt remains private.
    ref = track_id(request.GET.get("trackId"))
    order_id = request.GET.get("orderId", "")
    if ref and (not order_id or order_id == str(payment_id)):
        # Cancellation and success query values are untrusted; verify both paths.
        verify_zibal(payment_id, expected_track=ref)
    return redirect("finance:payment_result", payment_id=payment_id)


@never_cache
@login_required
@customer_required
@require_GET
def payment_result(request, payment_id):
    payment = owned_payment(request, payment_id)
    receipt = payment.verifications.filter(success=True).order_by("-created_at").first()
    latest = payment.verifications.order_by("-created_at").first()
    invoice = payment.invoices.first() if payment.status == Payment.Status.VERIFIED else None
    return render(request, "finance/payment_result.html", {
        "payment": payment, "invoice": invoice,
        "last_checked_at": latest.created_at if latest else None,
        "last_unpaid": bool(latest and latest.raw_payload.get("code") == 202),
        "bank_reference": (receipt.raw_payload.get("bank_reference", "") if receipt else ""),
    })


@never_cache
@login_required
@customer_required
@require_POST
def payment_recheck(request, payment_id):
    payment = owned_payment(request, payment_id)
    verify_zibal(payment.pk, expected_track=track_id(payment.provider_reference))
    return redirect("finance:payment_result", payment_id=payment.pk)
