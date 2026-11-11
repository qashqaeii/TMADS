from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import customer_required

from .models import SupportMessage, SupportTicket


@login_required
@customer_required
def ticket_list(request):
    tickets = SupportTicket.objects.filter(customer=request.user.customer_profile)
    return render(request, "support/list.html", {"tickets": tickets})


@login_required
@customer_required
def ticket_create(request):
    campaign_id = request.GET.get("campaign") or request.POST.get("campaign_id")
    if request.method == "POST":
        ticket = SupportTicket.objects.create(
            customer=request.user.customer_profile,
            subject=request.POST.get("subject", "سوال عمومی").strip() or "سوال عمومی",
            related_campaign_id=request.POST.get("campaign_id") or campaign_id or None,
        )
        SupportMessage.objects.create(
            ticket=ticket,
            author=request.user,
            body=request.POST.get("body", "").strip(),
        )
        messages.success(request, "تیکت ثبت شد.")
        return redirect("support:detail", ticket_id=ticket.id)
    return render(request, "support/create.html", {"campaign_id": campaign_id or ""})


@login_required
@customer_required
def ticket_detail(request, ticket_id):
    ticket = get_object_or_404(SupportTicket, id=ticket_id, customer=request.user.customer_profile)
    if request.method == "POST":
        SupportMessage.objects.create(
            ticket=ticket,
            author=request.user,
            body=request.POST.get("body", "").strip(),
        )
        return redirect("support:detail", ticket_id=ticket.id)
    return render(request, "support/detail.html", {"ticket": ticket})
