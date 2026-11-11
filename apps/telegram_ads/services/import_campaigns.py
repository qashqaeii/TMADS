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
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.services.sync import log_api_request, sync_ad_statistics_for

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
    project_name: str = "Hyper Tunnel",
    default_destination: str = HYPER_TUNNEL_BOT_URL,
    fetch_statistics: bool = True,
) -> tuple[int, int, int]:
    """
    Import Telegram Ads list items as local campaigns owned by ``customer``.

    Returns (created, updated, skipped).
    """
    client = TelegramAdsClient()
    items = client.list_advertisements()
    log_api_request("import_list_advertisements", True, {"count": len(items)})

    project, _ = AdvertisingProject.objects.get_or_create(
        customer=customer,
        name=project_name,
    )

    created = updated = skipped = 0
    for item in items:
        rid = _remote_id(item)
        if not rid:
            skipped += 1
            continue

        title = (item.get("title") or "").strip() or f"Ad {rid}"
        destination = (item.get("promote_url") or item.get("promotion_url") or default_destination).strip()
        status = map_remote_status_to_campaign(item)
        placement = _map_placement(item.get("placement"))
        objective = _infer_objective(item)
        cpm = item.get("cpm")
        ad_text = (item.get("text") or "").strip()

        with transaction.atomic():
            remote = TelegramAdvertisement.objects.filter(remote_ad_id=rid).select_related("campaign").first()
            if remote:
                campaign = remote.campaign
                if campaign.customer_id != customer.id:
                    skipped += 1
                    logger.warning("remote ad %s belongs to another customer; skipped", rid)
                    continue
                updated += 1
            else:
                campaign = Campaign.objects.create(
                    customer=customer,
                    project=project,
                    name=title,
                    status=status,
                    objective=objective,
                    destination=destination,
                    placement=placement or Campaign.Placement.SEARCH,
                    wizard_step=8,
                    wizard_data={"imported": True},
                )
                remote = TelegramAdvertisement.objects.create(campaign=campaign, remote_ad_id=rid)
                created += 1

            campaign.name = title
            campaign.status = status
            campaign.objective = objective
            campaign.destination = destination
            if placement:
                campaign.placement = placement
            if cpm is not None:
                try:
                    campaign.cpm_bid = Decimal(str(cpm))
                except Exception:
                    pass
            campaign.project = project
            campaign.save()

            remote.remote_status = str(item.get("status") or "")
            remote.remote_status_raw = item
            remote.placement = placement or remote.placement
            remote.promotion_url = destination
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
    """Remove wizard drafts with no Telegram link (local test data)."""
    ids_with_remote = TelegramAdvertisement.objects.filter(
        campaign__customer=customer,
    ).exclude(remote_ad_id="").values_list("campaign_id", flat=True)
    qs = Campaign.objects.filter(
        customer=customer,
        status=Campaign.Status.DRAFT,
        name__in=["", "کمپین جدید"],
    ).exclude(id__in=ids_with_remote)
    count, _ = qs.delete()
    return count
