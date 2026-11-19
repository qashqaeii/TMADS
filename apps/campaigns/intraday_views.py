"""Read-only 5-minute Telegram Ads statistics, never lifetime KPI substitutions."""
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.accounts.permissions import customer_required
from apps.campaigns.ownership import get_customer_campaign
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError


def _number(value):
    try:
        result = Decimal(str(value))
        return result if result.is_finite() and result >= 0 else None
    except (TypeError, ValueError, InvalidOperation):
        return None


@login_required
@customer_required
@require_GET
def campaign_intraday(request, campaign_id):
    campaign = get_customer_campaign(request.user.customer_profile, campaign_id)
    ad = campaign.remote_ads.exclude(remote_ad_id="").order_by("-updated_at").first()
    if not ad:
        return redirect("campaigns:detail", campaign_id=campaign.pk)

    try:
        hours = int(request.GET.get("hours", "24"))
    except ValueError:
        hours = 24
    if hours not in {6, 12, 24}:
        hours = 24
    key = f"tmads:intraday:v1:{ad.pk}:{hours}"
    points = cache.get(key)
    error = ""
    if points is None:
        try:
            # Valid API granularity: 300 seconds. Keep the full interval within 24h.
            end = timezone.now()
            start = end - timedelta(hours=hours)
            data = TelegramAdsClient().get_ad_statistics(
                ad.remote_ad_id, from_time=start, to_time=end, interval=300,
            )
            rows = data.get("items", []) if isinstance(data, dict) else []
            if not isinstance(rows, list):
                raise ValueError("پاسخ آمار معتبر نیست.")
            points = []
            for item in rows[:290]:
                if not isinstance(item, dict):
                    continue
                views = _number(item.get("views", item.get("impressions")))
                clicks = _number(item.get("clicks"))
                spent = _number(item.get("spent_budget")) if str(item.get("currency") or "").upper() == "TON" else None
                points.append({
                    "when": item.get("from_time"),
                    "views": int(views) if views is not None else None,
                    "clicks": int(clicks) if clicks is not None else None,
                    "spent": str(spent) if spent is not None else None,
                })
            points.sort(key=lambda row: int(row["when"] or 0), reverse=True)
            cache.set(key, points, 120)
        except (TelegramAdsError, ValueError, TypeError):
            error = "دریافت آمار درون‌روزی ممکن نشد. کمی بعد دوباره تلاش کنید."
            points = []
    total_views = sum((p["views"] or 0) for p in points if p["views"] is not None)
    total_clicks = sum((p["clicks"] or 0) for p in points if p["clicks"] is not None)
    return render(request, "campaigns/intraday.html", {
        "campaign": campaign, "ad": ad, "hours": hours, "points": points,
        "total_views": total_views, "total_clicks": total_clicks,
        "error": error, "partial": bool(points and any(p["views"] is None for p in points)),
    })
