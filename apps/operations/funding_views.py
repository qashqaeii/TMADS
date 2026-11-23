from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from apps.accounts.permissions import staff_ops_required
from apps.finance.funding_reconciliation import reconcile_uncertain_funding_transfer
from apps.finance.models import AccountFundingTransfer


@login_required
@staff_ops_required
@require_http_methods(["GET", "POST"])
def funding_transfers_ops(request):
    status = (request.GET.get("status") or AccountFundingTransfer.Status.UNCERTAIN).strip()
    if status not in AccountFundingTransfer.Status.values:
        status = AccountFundingTransfer.Status.UNCERTAIN
    qs = AccountFundingTransfer.objects.select_related(
        "connection__customer", "order", "operation__advertisement__campaign",
    ).order_by("-updated_at", "-created_at")
    if status != "all":
        qs = qs.filter(status=status)
    page_obj = Paginator(qs, 25).get_page(request.GET.get("page"))

    if request.method == "POST" and request.POST.get("action") == "reconcile":
        transfer = get_object_or_404(AccountFundingTransfer, pk=request.POST.get("transfer_id"))
        try:
            reconcile_uncertain_funding_transfer(transfer.pk, actor=request.user)
            messages.success(request, "نتیجه انتقال با وضعیت تلگرام تطبیق داده شد.")
        except Exception as exc:
            messages.error(request, str(exc))
        return redirect(request.path + f"?status={status}")

    return render(
        request,
        "operations/funding_transfers.html",
        {
            "page_obj": page_obj,
            "transfers": page_obj.object_list,
            "filter_status": status,
            "uncertain_count": AccountFundingTransfer.objects.filter(
                status=AccountFundingTransfer.Status.UNCERTAIN,
            ).count(),
        },
    )