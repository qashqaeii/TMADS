import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.accounts.permissions import customer_required
from apps.finance.gateways import get_payment_gateway

from .models import Invoice, Payment, RefundRequest, WalletLedgerEntry
from .refunds import create_refund_request, eligible_orders_for_refund
from .services import complete_topup_payment, ensure_wallet, verify_fake_payment


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
        if amount_irr < 10000:
            messages.error(request, "حداقل مبلغ شارژ ۱٬۰۰۰ تومان است.")
            return redirect("finance:topup")

        payment = Payment.objects.create(
            customer=request.user.customer_profile,
            order=None,
            amount_irr=amount_irr,
            gateway=_gateway_name(),
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
        if not result.success:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status", "updated_at"])
            messages.error(request, "درگاه پرداخت در دسترس نیست یا پیکربندی نشده است.")
            return redirect("finance:topup")

        payment.provider_reference = result.provider_reference
        payment.status = Payment.Status.REDIRECTED
        payment.save(update_fields=["provider_reference", "status", "updated_at"])

        redirect_url = (result.raw or {}).get("redirect_url")
        if redirect_url:
            return redirect(redirect_url)

        messages.info(request, "درگاه آزمایشی: پرداخت شبیه‌سازی می‌شود.")
        return redirect("finance:topup_callback", payment_id=payment.id)

    return render(
        request,
        "finance/topup.html",
        {"wallet": wallet, "payment_gateway": _gateway_name()},
    )


@login_required
@customer_required
def topup_callback(request, payment_id):
    payment = get_object_or_404(
        Payment,
        id=payment_id,
        customer=request.user.customer_profile,
    )
    if payment.status == Payment.Status.VERIFIED:
        return redirect("finance:wallet")

    gateway = get_payment_gateway()
    authority = request.GET.get("Authority") or payment.provider_reference
    status_param = request.GET.get("Status", "")

    if payment.gateway == "fake":
        gateway.verify_payment(provider_reference=payment.provider_reference, amount_irr=payment.amount_irr)
        if verify_fake_payment(payment):
            messages.success(request, "پرداخت آزمایشی با موفقیت تأیید شد و کیف پول شارژ شد.")
        else:
            messages.error(request, "تأیید پرداخت ناموفق بود.")
    elif status_param and status_param != "OK":
        payment.status = Payment.Status.FAILED
        payment.save(update_fields=["status", "updated_at"])
        messages.error(request, "پرداخت توسط کاربر لغو شد یا ناموفق بود.")
    else:
        payment.provider_reference = authority or payment.provider_reference
        payment.save(update_fields=["provider_reference", "updated_at"])
        result = gateway.verify_payment(
            provider_reference=payment.provider_reference,
            amount_irr=payment.amount_irr,
        )
        if result.success:
            complete_topup_payment(payment)
            messages.success(request, "پرداخت با موفقیت تأیید شد و کیف پول شارژ شد.")
        else:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status", "updated_at"])
            messages.error(request, "تأیید پرداخت در درگاه ناموفق بود.")

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
