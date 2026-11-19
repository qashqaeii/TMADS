from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import customer_required
from apps.campaigns.ownership import get_customer_campaign

from .models import SupportMessage, SupportTicket


@login_required
@customer_required
def ticket_list(request):
    tickets = SupportTicket.objects.filter(customer=request.user.customer_profile).order_by("-updated_at")
    return render(request, "support/list.html", {"tickets": tickets})


@login_required
@customer_required
@transaction.atomic
def ticket_create(request):
    customer = request.user.customer_profile
    campaign_id = request.POST.get("campaign_id") if request.method == "POST" else request.GET.get("campaign")
    campaign = get_customer_campaign(customer, campaign_id) if campaign_id else None
    pause = request.GET.get("intent") == "pause" and campaign is not None
    subject = f"درخواست توقف کمپین {campaign.name}"[:120] if pause else ""
    body = ""
    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()
        if not subject or len(subject) > 120 or not body or len(body) > 5000:
            messages.error(request, "موضوع (حداکثر ۱۲۰) و شرح درخواست (حداکثر ۵۰۰۰ نویسه) الزامی هستند.")
        else:
            ticket = SupportTicket.objects.create(
                customer=customer, subject=subject,
                related_campaign_id=campaign.pk if campaign else None,
            )
            SupportMessage.objects.create(ticket=ticket, author=request.user, body=body)
            messages.success(request, "تیکت ثبت شد؛ ثبت تیکت به معنی اجرای درخواست نیست.")
            return redirect("support:detail", ticket_id=ticket.id)
    return render(request, "support/create.html", {"campaign_id": campaign.pk if campaign else "",
        "campaign": campaign, "subject": subject, "body": body, "pause_request": pause})


@login_required
@customer_required
@transaction.atomic
def ticket_detail(request, ticket_id):
    tickets = SupportTicket.objects.filter(customer=request.user.customer_profile)
    if request.method == "POST":
        tickets = tickets.select_for_update()
    ticket = get_object_or_404(tickets, id=ticket_id)
    if request.method == "POST":
        body = request.POST.get("body", "").strip()
        if ticket.status in {SupportTicket.Status.CLOSED, SupportTicket.Status.RESOLVED}:
            messages.error(request, "این تیکت بسته است؛ برای درخواست جدید تیکت دیگری بسازید.")
        elif not body or len(body) > 5000:
            messages.error(request, "متن پیام (حداکثر ۵۰۰۰ نویسه) الزامی است.")
        else:
            SupportMessage.objects.create(ticket=ticket, author=request.user, body=body)
            ticket.save(update_fields=["updated_at"])
        return redirect("support:detail", ticket_id=ticket.id)
    return render(request, "support/detail.html", {"ticket": ticket})
