from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render,redirect,get_object_or_404
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from apps.accounts.permissions import customer_required,staff_ops_required
from apps.telegram_ads.models import RelatedAccountRequest
from apps.telegram_ads.services.related_accounts import RelatedAccountForm,request_account,execute_account,reject_account,provisioning_enabled
from apps.telegram_ads.exceptions import TelegramAdsError

@login_required
@customer_required
@require_http_methods(["GET","POST"])
def customer_related_account(request):
    row=RelatedAccountRequest.objects.filter(customer=request.user.customer_profile).first()
    form=RelatedAccountForm(request.POST or None)
    if request.method=="POST" and form.is_valid():
        try:
            request_account(request.user,request.POST)
            messages.success(request,"درخواست ایجاد حساب ثبت شد؛ هنوز حسابی در تلگرام ایجاد نشده است.")
            return redirect("accounts:related_account")
        except ValueError as exc:
            messages.error(request,str(exc))
    return render(request,"accounts/related_account.html",{"row":row,"form":form})

@login_required
@staff_ops_required
@require_http_methods(["GET","POST"])
def ops_related_accounts(request):
    if request.method=="POST":
        row=get_object_or_404(RelatedAccountRequest,pk=request.POST.get("id"))
        try:
            if request.POST.get("action")=="execute":
                execute_account(row.pk,request.user)
                messages.success(request,"هویت حساب ایجادشده از API تأیید شد.")
            elif request.POST.get("action")=="reject":
                reject_account(row.pk,request.user,request.POST.get("note",""))
                messages.success(request,"تصمیم ثبت شد.")
            else:
                raise ValueError("اقدام نامعتبر است.")
        except (ValueError,TelegramAdsError) as exc:
            messages.error(request,str(exc))
        return redirect("operations:related_accounts")
    page=Paginator(RelatedAccountRequest.objects.select_related("customer"),20).get_page(request.GET.get("page"))
    return render(request,"operations/related_accounts.html",{"page_obj":page,"enabled":provisioning_enabled()})
