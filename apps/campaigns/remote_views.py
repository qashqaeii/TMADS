from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from apps.accounts.permissions import customer_required, staff_ops_required
from apps.campaigns.ownership import get_customer_campaign
from apps.campaigns.models import RemoteAdOperation
from apps.telegram_ads.services.manage_ad import request_operation, execute_operation, reject_operation
from apps.telegram_ads.exceptions import TelegramAdsError
from django.shortcuts import get_object_or_404


@login_required
@customer_required
@require_http_methods(["GET","POST"])
def remote_management(request, campaign_id):
    campaign=get_customer_campaign(request.user.customer_profile,campaign_id)
    if request.method=="POST":
        try:
            request_operation(campaign.pk,actor=request.user,action=request.POST.get("action",""),value=request.POST.get("value",""))
            messages.success(request,"درخواست ثبت شد؛ هنوز تغییری در تلگرام انجام نشده است.")
        except ValueError as exc:
            messages.error(request,str(exc))
        return redirect("campaigns:remote_management",campaign_id=campaign.pk)
    ads=list(campaign.remote_ads.exclude(remote_ad_id="")[:2])
    return render(request,"campaigns/remote_management.html",{
        "campaign":campaign,"ad":ads[0] if len(ads)==1 else None,
        "operations":RemoteAdOperation.objects.filter(advertisement__campaign=campaign)[:30],
    })


@login_required
@staff_ops_required
@require_http_methods(["GET","POST"])
def remote_operations(request):
    if request.method=="POST":
        op=get_object_or_404(RemoteAdOperation,pk=request.POST.get("operation_id"))
        try:
            if request.POST.get("decision")=="execute":
                execute_operation(op.pk,actor=request.user)
                messages.success(request,"نتیجه عملیات از تلگرام تأیید شد.")
            elif request.POST.get("decision")=="reject":
                reject_operation(op.pk,actor=request.user,reason=request.POST.get("reason",""))
                messages.success(request,"تصمیم ثبت شد.")
            else:
                raise ValueError("تصمیم معتبر نیست.")
        except (ValueError,TelegramAdsError) as exc:
            messages.error(request,str(exc))
        return redirect("operations:remote_operations")
    from django.core.paginator import Paginator
    qs=RemoteAdOperation.objects.select_related("advertisement__campaign__customer")
    status=request.GET.get("status","pending")
    if status in RemoteAdOperation.Status.values:
        qs=qs.filter(status=status)
    page=Paginator(qs,30).get_page(request.GET.get("page"))
    return render(request,"operations/remote_operations.html",{"page_obj":page,"statuses":RemoteAdOperation.Status.choices,"filter_status":status})
