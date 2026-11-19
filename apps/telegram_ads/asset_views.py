from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.cache import never_cache
from apps.accounts.permissions import customer_required
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.customer_assets import owned_account, verified_client, enabled, issue_nonce, create_asset, change_audience_contacts, EVENT_TYPES

@login_required
@customer_required
@never_cache
@require_http_methods(["GET","POST"])
def customer_assets(request):
    row=owned_account(request.user)
    if request.method=="POST":
        try:
            create_asset(request.user,request.POST)
            messages.success(request,"شناسه منبع از تلگرام دریافت شد.")
        except (ValueError,TelegramAdsError) as exc:
            messages.error(request,str(exc))
        return redirect("accounts:advertiser_assets")
    section=request.GET.get("section","audiences")
    if section not in {"audiences","pixel","events"}:
        section="audiences"
    ctx={"row":row,"section":section,"enabled":enabled(),"event_types":EVENT_TYPES,"loaded":False}
    if row:
        ctx.update(nonce=issue_nonce(row),operations=row.asset_operations.all()[:10],
            unresolved=row.asset_operations.filter(state__in=["executing","uncertain"]).exists())
        if request.GET.get("load")=="1":
            try:
                offset=max(0,min(10000,int(request.GET.get("offset","0"))))
                client=verified_client(row)
                kwargs={"account_id":row.remote_account_id}
                if section=="pixel":
                    ctx["pixel"]=client.get_pixel_info(**kwargs)
                else:
                    data=(client.get_audiences(offset=offset,limit=50,**kwargs) if section=="audiences"
                          else client.get_pixel_events(offset=offset,limit=50,**kwargs))
                    items=data.get(section)
                    if not isinstance(items,list):
                        raise ValueError("ساختار پاسخ معتبر نیست.")
                    ctx.update(items=items,offset=offset,previous=offset-50 if offset>=50 else None,
                        next_offset=offset+50 if len(items)==50 else None)
                ctx["loaded"]=True
            except (ValueError,TelegramAdsError):
                ctx["load_error"]="دریافت منابع حساب ممکن نشد. وضعیت دسترسی و ارتباط را بررسی کنید."
    return render(request,"accounts/advertiser_assets.html",ctx)


@login_required
@customer_required
@never_cache
@require_POST
def customer_audience_update(request):
    try:
        change_audience_contacts(request.user, request.POST)
        messages.success(request, "درخواست تغییر مخاطبان توسط API تأیید شد؛ اندازه گروه ممکن است تخمینی باشد.")
    except (ValueError, TelegramAdsError):
        messages.error(request, "تغییر مخاطبان انجام نشد یا نتیجه آن نیازمند تطبیق است؛ بدون بررسی دوباره ارسال نکنید.")
    return redirect("accounts:advertiser_assets")
