import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.permissions import customer_required
from apps.finance.gateways import get_payment_gateway

from .models import Invoice, Payment, PaymentVerification, RefundRequest, WalletLedgerEntry
from .refunds import create_refund_request, eligible_orders_for_refund
from .services import complete_topup_payment, ensure_wallet, verify_fake_payment
from .zibal_views import initiate_zibal


def _gateway_name() -> str:
    return (settings.PAYMENT_GATEWAY or "fake").lower()


@login_required
@customer_required
def wallet_view(request):
    wallet = ensure_wallet(request.user.customer_profile)
    recent = wallet.ledger_entries.all()[:20]
    return render(
        request,
        "finance/wallet.html",
        {
            "wallet": wallet,
            "recent_entries": recent,
            "recent_payments": Payment.objects.filter(customer=request.user.customer_profile, gateway="zibal", order__isnull=True)[:10],
        },
    )


@login_required
@customer_required
def topup_view(request):
    wallet = ensure_wallet(request.user.customer_profile)
    if request.method == "POST":
        try:
            amount_toman = int(request.POST.get("amount_toman", "0"))
        except ValueError:
            amount_toman = 0
        amount_irr = amount_toman * 10
        if amount_irr > 9223372036854775807:
            messages.error(request, "مبلغ شارژ از محدوده مجاز بیشتر است.")
            return redirect("finance:topup")
        if amount_irr < 10000:
            messages.error(request, "حداقل مبلغ شارژ ۱٬۰۰۰ تومان است.")
            return redirect("finance:topup")

        if _gateway_name() == "zibal":
            return initiate_zibal(request, amount_irr)

        payment = Payment.objects.create(
            customer=request.user.customer_profile,
            order=None,
            amount_irr=amount_irr,
            gateway=_gateway_name(),
            provider_amount_irr=amount_irr if _gateway_name() == "zarinpal" else None,
            provider_reference="",
            idempotency_key=str(uuid.uuid4()),
        )
        callback_url = request.build_absolute_uri(
            reverse("finance:topup_callback", kwargs={"payment_id": payment.id})
        )
        gateway = get_payment_gateway()
        result = gateway.create_payment(
            amount_irr=amount_irr,
            callback_url=callback_url,
            description=f"topup-{payment.id}",
        )
        if not result.success or not result.provider_reference:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status", "updated_at"])
            messages.error(request, "درگاه پرداخت در دسترس نیست یا پیکربندی نشده است.")
            return redirect("finance:topup")

        payment.provider_reference = result.provider_reference
        payment.status = Payment.Status.REDIRECTED
        try:
            with transaction.atomic():
                payment.save(update_fields=["provider_reference", "status", "updated_at"])
        except IntegrityError:
            Payment.objects.filter(pk=payment.pk).update(status=Payment.Status.FAILED)
            messages.error(request, "شناسه تکراری درگاه؛ پرداخت متوقف شد. با پشتیبانی تماس بگیرید.")
            return redirect("finance:topup")

        redirect_url = (result.raw or {}).get("redirect_url")
        if redirect_url:
            return redirect(redirect_url)

        messages.info(request, "درگاه آزمایشی: پرداخت شبیه‌سازی می‌شود.")
        return redirect("finance:topup_callback", payment_id=payment.id)

    return render(
        request,
        "finance/topup.html",
        {"wallet": wallet, "payment_gateway": _gateway_name(), "payment_nonce": str(uuid.uuid4())},
    )


@login_required
@customer_required
@require_GET
@transaction.atomic
def topup_callback(request, payment_id):
    payment = get_object_or_404(
        Payment.objects.select_for_update(),
        id=payment_id, customer=request.user.customer_profile,
    )
    if payment.status == Payment.Status.VERIFIED:
        return redirect("finance:wallet")
    if payment.order_id is not None or payment.status != Payment.Status.REDIRECTED or not payment.provider_reference:
        messages.error(request, "پرداخت معتبر یا آماده بررسی نیست.")
        return redirect("finance:wallet")
    if payment.gateway == "fake":
        if verify_fake_payment(payment):
            messages.success(request, "پرداخت آزمایشی با موفقیت تأیید شد و کیف پول شارژ شد.")
        else:
            messages.error(request, "پرداخت آزمایشی مجاز نیست.")
        return redirect("finance:wallet")

    authority = request.GET.get("Authority", "")
    status_param = request.GET.get("Status", "")
    if payment.gateway != "zarinpal" or authority != payment.provider_reference:
        messages.error(request, "شناسه پرداخت با سفارش ثبت‌شده مطابقت ندارد.")
        return redirect("finance:wallet")
    if status_param != "OK":
        messages.warning(request, "پرداخت تکمیل نشده؛ در صورت پرداخت از پشتیبانی پیگیری کنید.")
        return redirect("finance:wallet")

    # Old pending payments were created without an explicit currency contract.
    # Do not reinterpret them with the new Rial adapter.
    if payment.provider_amount_irr != payment.amount_irr:
        messages.error(request, "مبلغ این پرداخت قدیمی نیازمند بررسی پشتیبانی است.")
        return redirect("finance:wallet")
    gateway = get_payment_gateway(payment.gateway)
    result = gateway.verify_payment(provider_reference=payment.provider_reference, amount_irr=payment.provider_amount_irr)
    PaymentVerification.objects.create(
        payment=payment, success=result.success,
        raw_payload={"provider_reference_matched": result.provider_reference == payment.provider_reference,
                     "amount_irr": payment.provider_amount_irr,
                     "code": ((result.raw or {}).get("response") or {}).get("data", {}).get("code")},
    )
    if result.success and result.provider_reference == payment.provider_reference:
        complete_topup_payment(payment)
        messages.success(request, "پرداخت با موفقیت تأیید شد و کیف پول شارژ شد.")
    else:
        # An uncertain external result must remain retryable; never mark verified on callback data alone.
        messages.error(request, "تأیید پرداخت هنوز انجام نشده است. دوباره تلاش کنید یا با پشتیبانی تماس بگیرید.")
    return redirect("finance:wallet")

@login_required
@customer_required
def transactions_view(request):
    wallet = ensure_wallet(request.user.customer_profile)
    entries = WalletLedgerEntry.objects.filter(wallet=wallet)[:100]
    return render(request, "finance/transactions.html", {"entries": entries})


@login_required
@customer_required
def invoices_view(request):
    invoices = Invoice.objects.filter(customer=request.user.customer_profile)[:100]
    return render(request, "finance/invoices.html", {"invoices": invoices})


@login_required
@customer_required
def invoice_detail(request, invoice_id):
    invoice = get_object_or_404(
        Invoice,
        id=invoice_id,
        customer=request.user.customer_profile,
    )
    return render(request, "finance/invoice_detail.html", {"invoice": invoice})


@login_required
@customer_required
def refunds_view(request):
    customer = request.user.customer_profile
    refunds = RefundRequest.objects.filter(customer=customer)[:50]
    eligible = eligible_orders_for_refund(customer)
    if request.method == "POST":
        order_id = request.POST.get("order_id")
        reason = request.POST.get("reason", "").strip()
        from .models import AdvertisingOrder

        order = get_object_or_404(AdvertisingOrder, id=order_id, customer=customer)
        try:
            create_refund_request(customer=customer, order=order, reason=reason)
            messages.success(request, "درخواست بازپرداخت ثبت شد و در صف بررسی عملیات است.")
            return redirect("finance:refunds")
        except ValueError as exc:
            messages.error(request, str(exc))
    from apps.campaigns.models import Campaign

    names = {
        str(c.id): c.name or "کمپین"
        for c in Campaign.objects.filter(
            customer=customer,
            id__in=[o.campaign_id for o in eligible],
        )
    }
    order_choices = []
    for order in eligible:
        title = names.get(str(order.campaign_id), str(order.campaign_id)[:8])
        order_choices.append((order.id, f"{title} — {order.total_irr // 10:,} تومان"))
    return render(
        request,
        "finance/refunds.html",
        {"refunds": refunds, "order_choices": order_choices},
    )
