import uuid

from .models import Invoice, Payment  # noqa: F401 — AdvertisingOrder via order FK


def next_invoice_number() -> str:
    return f"INV-{uuid.uuid4().hex[:10].upper()}"


def issue_invoice_for_order(order, customer, *, description: str = "پرداخت کمپین") -> Invoice:
    existing = Invoice.objects.filter(order=order, description=description).first()
    if existing:
        return existing
    return Invoice.objects.create(
        customer=customer,
        payment=None,
        order=order,
        invoice_number=next_invoice_number(),
        amount_irr=order.total_irr,
        description=description,
        meta={"campaign_id": str(order.campaign_id)},
    )


def issue_invoice_for_payment(payment: Payment, *, description: str = "") -> Invoice:
    existing = Invoice.objects.filter(payment=payment).first()
    if existing:
        return existing
    return Invoice.objects.create(
        customer=payment.customer,
        payment=payment,
        order=payment.order,
        invoice_number=next_invoice_number(),
        amount_irr=payment.amount_irr,
        description=description or "شارژ کیف پول",
        meta={"gateway": payment.gateway},
    )
