"""Read-only five-minute reporting, kept separate from daily snapshots."""
from datetime import datetime, timezone as utc_timezone
from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from apps.accounts.permissions import customer_required
from apps.campaigns.ownership import get_customer_campaign
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError

def normalize_rows(items,start,end):
    if not isinstance(items,list) or len(items)>288:
        raise ValueError("invalid response")
    result={}
    for item in items:
        if not isinstance(item,dict):
            raise ValueError("invalid item")
        ts=item.get("from_time")
        if type(ts) is not int or ts%300 or not start<=ts<end or ts in result or item.get("to_time")!=ts+300:
            raise ValueError("invalid interval")
        counts={}
        for key in ("views","clicks","opens","actions"):
            value=item.get(key)
            counts[key]=value if type(value) is int and value>=0 else None
        currency=item.get("currency")
        currency=currency if currency in {"TON","EUR","XTR"} else None
        try:
            spent=Decimal(str(item.get("spent_budget")))
            if not spent.is_finite() or spent<0 or not currency:
                spent=None
        except (InvalidOperation,ValueError):
            spent=None
        result[ts]={"time":datetime.fromtimestamp(ts,tz=utc_timezone.utc),**counts,"currency":currency,"spent":spent}
    return [result[k] for k in sorted(result,reverse=True)]

@login_required
@customer_required
@never_cache
@require_GET
def campaign_intraday(request,campaign_id):
    campaign=get_customer_campaign(request.user.customer_profile,campaign_id)
    ads=list(campaign.remote_ads.exclude(remote_ad_id="")[:2])
    hours=6 if request.GET.get("hours")=="6" else 24
    ctx={"campaign":campaign,"hours":hours,"loaded":False}
    if len(ads)!=1:
        ctx["error"]="برای آمار دقیق، کمپین باید دقیقاً یک تبلیغ متصل داشته باشد."
    elif request.GET.get("load")=="1":
        key=f"intraday:v1:{campaign.customer_id}:{ads[0].pk}:{hours}"
        cached=cache.get(key)
        if cached is not None:
            ctx.update(cached)
        elif not cache.add(f"intraday-limit:{campaign.customer_id}",True,timeout=20):
            ctx["error"]="لطفاً چند ثانیه صبر کنید."
        else:
            end=int(timezone.now().timestamp())//300*300
            start=end-hours*3600
            try:
                stats=TelegramAdsClient().get_ad_statistics(ads[0].remote_ad_id,from_time=start,to_time=end,interval=300)
                rows=normalize_rows(stats.get("items"),start,end)
                data={"rows":rows,"loaded":True,"fetched_at":timezone.now(),"slots":hours*12,"count":len(rows)}
                cache.set(key,data,timeout=60)
                ctx.update(data)
            except (TelegramAdsError,ValueError,TypeError,AttributeError):
                ctx["error"]="آمار پنج‌دقیقه‌ای قابل دریافت یا تأیید نبود؛ آمار روزانه تغییر نکرد."
    return render(request,"campaigns/intraday.html",ctx)
