from __future__ import annotations

import logging
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CustomerProfile
from apps.telegram_ads.constants import API_TO_TMADS_PLACEMENT
from apps.campaigns.models import (
    AdCreative,
    AdvertisingProject,
    Campaign,
    CampaignTargeting,
    TelegramAdvertisement,
)
from django.core.exceptions import PermissionDenied

from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.models import TelegramAdsConnection
from apps.telegram_ads.services.account_connections import connection_client, default_connection
from apps.telegram_ads.services.sync import has_financial_lock, log_api_request, sync_ad_statistics_for
from apps.campaigns.deletion import delete_draft_campaign
from apps.campaigns.metrics import _decimal

logger = logging.getLogger(__name__)

HYPER_TUNNEL_BOT_URL = "https://t.me/HyperTunnelbot"

from apps.telegram_ads.status_map import map_remote_status_to_campaign


def _remote_id(item: dict) -> str:
    return str(item.get("ad_id") or item.get("id") or "").strip()


def _map_placement(raw: str | None) -> str:
    if not raw:
        return ""
    value = raw.replace("-", "_").lower()
    if value in API_TO_TMADS_PLACEMENT:
        return API_TO_TMADS_PLACEMENT[value]
    aliases = {
        "search": Campaign.Placement.SEARCH,
        "search_result": Campaign.Placement.SEARCH,
        "bot_banner": Campaign.Placement.BOT_BANNER,
        "channels": Campaign.Placement.CHANNELS,
        "channel_post": Campaign.Placement.CHANNELS,
        "video": Campaign.Placement.VIDEO,
        "video_banner": Campaign.Placement.VIDEO,
    }
    return aliases.get(value, value if value in Campaign.Placement.values else "")


def _infer_objective(item: dict) -> str:
    url = (item.get("promote_url") or item.get("promotion_url") or "").lower()
    action = str(item.get("action_type") or "").lower()
    if "t.me/" in url and "bot" in url:
        return Campaign.Objective.BOT
    if "start" in action or "bot" in action:
        return Campaign.Objective.BOT
    if "channel" in url:
        return Campaign.Objective.CHANNEL
    return Campaign.Objective.BOT


def _list_import_items(client, connection: TelegramAdsConnection | None) -> list[dict]:
    if connection and connection.connection_type == TelegramAdsConnection.Type.PLATFORM_MANAGED:
        items, offset, seen = [], None, set()
        for _ in range(1000):
            page = client.get_account_ads_page(
                account_id=connection.remote_account_id, offset=offset, limit=100,
            )
            ads = page.get("ads") or []
            if not isinstance(ads, list):
                raise ValueError("ساختار فهرست تبلیغات معتبر نیست.")
            for row in ads:
                ad_id = row.get("ad_id")
                if type(ad_id) is int and ad_id > 0 and ad_id not in seen:
                    seen.add(ad_id)
                    items.append(row)
            offset = page.get("next_offset")
            if not offset:
                return items
            if not ads:
                raise ValueError("صفحه‌بندی تبلیغات کامل نشد.")
        raise ValueError("سقف امن صفحه‌بندی تبلیغات رسید.")
    return client.list_advertisements()


def resolve_import_customer(*, username: str | None = None) -> CustomerProfile:
    User = get_user_model()
    if username:
        user = User.objects.get(username=username)
    else:
        user = User.objects.filter(is_superuser=True).order_by("id").first()
        if not user:
            raise ValueError("سوپر‌یوزری یافت نشد.")
    profile = CustomerProfile.objects.filter(user=user).first()
    if not profile:
        raise ValueError(f"پروفایل مشتری برای {user.username} وجود ندارد.")
    return profile


def import_remote_campaigns_for_customer(
    customer: CustomerProfile,
    *,
    connection: TelegramAdsConnection | None = None,
    project_name: str = "Hyper Tunnel",
    default_destination: str = HYPER_TUNNEL_BOT_URL,
    fetch_statistics: bool = True,
) -> tuple[int, int, int]:
    """
    Import Telegram Ads list items as local campaigns owned by ``customer``.

    Returns (created, updated, skipped).
    """
    if connection is not None and connection.customer_id != customer.id:
        raise PermissionDenied
    if connection is None:
        connection = default_connection(customer)
    if connection:
        client = connection_client(connection)
    else:
        client = TelegramAdsClient()
    items = _list_import_items(client, connection)
    log_api_request(
        "import_list_advertisements", True,
        {"count": len(items), "connection_id": str(connection.pk) if connection else ""},
    )

    project, _ = AdvertisingProject.objects.get_or_create(
        customer=customer,
        name=project_name,
    )

    created = updated = skipped = 0
    for item in items:
        rid = _remote_id(item)
        if not rid.isascii() or not rid.isdigit() or len(rid) > 64 or int(rid) <= 0:
            skipped += 1
            continue

        title = (str(item.get("title") or "").strip() or f"Ad {rid}")[:200]
        # Never infer a missing promotion destination from the project name.
        destination = str(item.get("promote_url") or item.get("promotion_url") or "").strip()[:500]
        status = map_remote_status_to_campaign(item)
        placement = _map_placement(item.get("placement"))
        objective = _infer_objective(item)
        cpm = item.get("cpm")
        ad_text = (item.get("text") or "").strip()

        with transaction.atomic():
            remote = TelegramAdvertisement.objects.filter(remote_ad_id=rid).select_related("campaign").first()
            if remote:
                campaign = Campaign.objects.select_for_update().get(pk=remote.campaign_id)
                if campaign.customer_id != customer.id:
                    skipped += 1
                    logger.warning("remote ad %s belongs to another customer; skipped", rid)
                    continue
                if has_financial_lock(campaign) or campaign.status in {Campaign.Status.CANCELLED, Campaign.Status.FAILED}:
                    skipped += 1
                    continue
                updated += 1
            else:
                campaign = Campaign.objects.create(
                    customer=customer,
                    project=project,
                    telegram_connection=connection,
                    name=title,
                    status=status,
                    objective=objective,
                    destination=destination,
                    placement=placement,
                    wizard_step=5,
                    wizard_data={"imported": True, "connection_id": str(connection.pk) if connection else ""},
                )
                remote = TelegramAdvertisement.objects.create(
                    campaign=campaign,
                    remote_ad_id=rid,
                    remote_account_id=connection.remote_account_id if connection else "",
                )
                created += 1

            campaign.name = title
            campaign.status = status
            campaign.objective = objective
            campaign.destination = destination
            if connection and not campaign.telegram_connection_id:
                campaign.telegram_connection = connection
            if placement:
                campaign.placement = placement
            cpm_ton = _decimal(cpm) if item.get("currency") == "TON" else None
            if cpm_ton is not None and cpm_ton < Decimal("100000000"):
                campaign.cpm_bid = cpm_ton
            # A repeat import must not reassign an existing project.
            if not campaign.project_id:
                campaign.project = project
            campaign.save()

            remote.remote_status = str(item.get("status") or "")
            remote.remote_status_raw = item
            remote.placement = placement or remote.placement
            remote.promotion_url = destination
            if connection and connection.remote_account_id:
                remote.remote_account_id = connection.remote_account_id
            remote.save()

            creative = campaign.creatives.first()
            if not creative:
                creative = AdCreative(campaign=campaign)
            creative.title = title[:200]
            if ad_text:
                creative.ad_text = ad_text
            creative.cta_label = (item.get("button") or "")[:64]
            creative.save()

            target = item.get("target")
            if isinstance(target, dict) and target:
                CampaignTargeting.objects.update_or_create(
                    campaign=campaign,
                    defaults={"config": {"api_target": target, "source": "import"}},
                )

        if fetch_statistics:
            try:
                sync_ad_statistics_for(remote)
            except Exception as exc:
                logger.info("stats sync skipped for %s: %s", rid, exc)

    return created, updated, skipped


def prune_empty_draft_campaigns(customer: CustomerProfile) -> int:
    """Delete only genuinely untouched local drafts, not names that look empty."""
    from apps.finance.models import AdvertisingOrder

    ids_with_remote = TelegramAdvertisement.objects.filter(
        campaign__customer=customer,
    ).exclude(remote_ad_id="").values_list("campaign_id", flat=True)
    ids_with_order = AdvertisingOrder.objects.filter(customer=customer).values_list("campaign_id", flat=True)
    qs = Campaign.objects.filter(
        customer=customer,
        status=Campaign.Status.DRAFT,
        name__in=["", "کمپین جدید"],
        destination="", budget_irr=0, draft_revision=0, draft_saved_at__isnull=True,
        wizard_step=1, wizard_data={}, ad_settings={}, creatives__isnull=True,
        targeting__isnull=True,
    ).exclude(id__in=ids_with_remote).exclude(id__in=ids_with_order)
    deleted = 0
    for campaign in qs.distinct().iterator():
        with transaction.atomic():
            current = Campaign.objects.select_for_update().filter(pk=campaign.pk).first()
            if current is None or not qs.filter(pk=current.pk).exists():
                continue
            try:
                delete_draft_campaign(current)
                deleted += 1
            except ValueError:
                continue
    return deleted
