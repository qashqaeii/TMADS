"""Staff-only, on-demand read surface. Never exposes shared account data to customers."""
from datetime import datetime, timezone as utc_timezone
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.utils import timezone

from apps.accounts.permissions import staff_ops_required
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError

SECTIONS = [
    ("report","گزارش ماهانه"), ("stats","آمار دوره‌ای"), ("transactions","تراکنش حساب"),
    ("transfer","وضعیت انتقال"), ("accounts","حساب‌های مرتبط"), ("audiences","مخاطبان"), ("pixels","پیکسل و رویدادها"),
]
COLS = {
    "report":[("ad_id","شناسه"),("ad_title","عنوان تبلیغ"),("views","نمایش"),("opens","بازشدن ویدیو"),("clicks","کلیک"),("actions","اقدام"),("spent_budget","هزینه"),("currency","ارز")],
    "stats":[("from_time","شروع UTC"),("views","نمایش"),("opens","بازشدن ویدیو"),("clicks","کلیک"),("actions","اقدام"),("spent_budget","هزینه"),("currency","ارز")],
    "transactions":[("date","زمان UTC"),("peer_type","نوع تراکنش"),("amount","مبلغ"),("currency","ارز")],
    "transfer":[("transaction_id","شناسه"),("status","وضعیت"),("amount","مبلغ"),("currency","ارز")],
    "accounts":[("account_id","شناسه حساب"),("title","عنوان"),("remaining_budget","اعتبار آزاد"),("ads_budget","اعتبار تبلیغات"),("spent_budget","مصرف"),("currency","ارز")],
    "audiences":[("audience_id","شناسه"),("title","عنوان"),("size","اندازه تقریبی"),("ads_count","تعداد تبلیغات")],
    "pixels":[("event_id","شناسه رویداد"),("title","عنوان"),("type","نوع"),("status","وضعیت"),("ads_count","تعداد تبلیغات")],
}


def _integer(raw, low, high, label):
    try:
        value=int(raw)
        if not low<=value<=high:
            raise ValueError
        return value
    except (TypeError,ValueError):
        raise ValueError(label+" معتبر نیست.") from None


def _rows(items,section):
    if not isinstance(items,list) or any(not isinstance(x,dict) for x in items):
        raise ValueError("ساختار پاسخ گزارش معتبر نیست.")
    output=[]
    for item in items:
        row=dict(item)
        if section=="transactions":
            peer=row.get("peer")
            row["peer_type"]=peer.get("type") if isinstance(peer,dict) else None
        for key in ("date","from_time"):
            if key in row:
                try:
                    row[key]=datetime.fromtimestamp(int(row[key]),tz=utc_timezone.utc).strftime("%Y-%m-%d %H:%M")
                except (ValueError,TypeError,OverflowError,OSError):
                    row[key]=None
        output.append([row.get(key) if isinstance(row.get(key),(str,int,float)) else "—" for key,_ in COLS[section]])
    return [[value if value is not None and value!="" else "—" for value in row] for row in output]


@login_required
@staff_ops_required
@require_GET
def account_workspace(request):
    now=timezone.now()
    section=request.GET.get("section","report")
    if section not in COLS:
        section="report"
    ctx={"sections":SECTIONS,"section":section,"columns":[label for _,label in COLS[section]],
         "year":request.GET.get("year",now.year),"month":request.GET.get("month",now.month),
         "interval":request.GET.get("interval","86400"),"transaction_id":request.GET.get("transaction_id","")[:128],
         "offset":request.GET.get("offset",""),"loaded":False}
    if request.GET.get("load")!="1":
        return render(request,"operations/telegram_account.html",ctx)
    try:
        key=f"tmads:ops:account_report:{request.user.pk}"
        if not cache.add(key,True,2):
            raise ValueError("لطفاً چند لحظه صبر کنید و دوباره تلاش کنید.")
        client=TelegramAdsClient()
        offset=0
        next_offset=None
        if section=="report":
            year=_integer(ctx["year"],2021,2100,"سال")
            month=_integer(ctx["month"],1,12,"ماه")
            items=client.get_account_report(year,month)
        elif section=="stats":
            interval=_integer(ctx["interval"],300,86400,"بازه")
            if interval not in {300,86400}:
                raise ValueError("بازه باید روزانه یا پنج دقیقه‌ای باشد.")
            end=int(now.timestamp())//interval*interval
            start=end-(288 if interval==300 else 30)*interval
            items=client.get_account_statistics(from_time=start,to_time=end,interval=interval)
        elif section=="transfer":
            tx=ctx["transaction_id"].strip()
            if not tx or len(request.GET.get("transaction_id",""))>128:
                raise ValueError("شناسه انتقال معتبر نیست.")
            item=client.get_transaction_status(tx)
            if item.get("transaction_id")!=tx:
                raise ValueError("شناسه پاسخ با درخواست مطابقت ندارد.")
            items=[item]
        elif section=="transactions":
            cursor=ctx["offset"][:512] or None
            data=client.get_account_transactions(offset=cursor,limit=50)
            items=data.get("transactions")
            next_offset=data.get("next_offset")
        else:
            offset=_integer(ctx["offset"] or "0",0,1000000,"صفحه")
            if section=="accounts":
                data=client.get_related_accounts(offset=offset,limit=50)
                items=data.get("accounts")
            elif section=="audiences":
                data=client.get_audiences(offset=offset,limit=50)
                items=data.get("audiences")
            else:
                data=client.get_pixel_events(offset=offset,limit=50)
                items=data.get("events")
            total=data.get("total_count")
            if isinstance(items,list) and type(total) is int and items and offset+len(items)<total:
                next_offset=offset+len(items)
        rows=_rows(items,section)
        ctx.update({"loaded":True,"rows":rows,"next_offset":next_offset,"row_count":len(rows),"fetched_at":timezone.now()})
        if request.GET.get("export")=="csv":
            import csv
            response=HttpResponse(content_type="text/csv; charset=utf-8")
            response["Content-Disposition"]='attachment; filename="telegram-account-report.csv"'
            response.write("\ufeff")
            writer=csv.writer(response)
            writer.writerow(ctx["columns"])
            for row in rows:
                writer.writerow(["'"+str(v) if isinstance(v,str) and v.lstrip().startswith(("=","+","-","@","\t","\r")) else v for v in row])
            response["Cache-Control"]="private, no-store"
            return response
    except ValueError as exc:
        ctx["error"]=str(exc)
    except TelegramAdsError:
        ctx["error"]="اطلاعات از تلگرام دریافت نشد؛ وضعیت مجوز یا اتصال را بررسی کنید."
    response=render(request,"operations/telegram_account.html",ctx)
    response["Cache-Control"]="private, no-store"
    return response
