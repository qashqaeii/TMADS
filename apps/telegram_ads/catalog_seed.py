"""Curated TargetBotCatalogEntry rows for Similar Bots (real public bot usernames)."""

from __future__ import annotations

from typing import Any

# monthly_users only when observed from a trusted Ads UI sample; otherwise omit.
DEFAULT_BOT_CATALOG: list[dict[str, Any]] = [
    {
        "username": "@CityNetworkbot",
        "title": "City Network",
        "category": "vpn",
        "tags": ["vpn", "network"],
        "language_codes": ["fa", "en"],
        "priority": 20,
    },
    {
        "username": "@Unknownvpnbot",
        "title": "Unknown Vpn",
        "category": "vpn",
        "tags": ["vpn"],
        "language_codes": ["fa", "en"],
        "monthly_users": 6481,
        "priority": 18,
    },
    {
        "username": "@tonvpn_bot",
        "title": "Ton VPN",
        "category": "vpn",
        "tags": ["vpn", "ton"],
        "language_codes": ["fa", "en"],
        "monthly_users": 37587,
        "priority": 22,
    },
    {
        "username": "@NullNetworkBot",
        "title": "Null Network",
        "category": "vpn",
        "tags": ["vpn", "network"],
        "language_codes": ["fa", "en"],
        "monthly_users": 17541,
        "priority": 18,
    },
    {
        "username": "@AVAVPN_bot",
        "title": "AVA Connect",
        "category": "vpn",
        "tags": ["vpn"],
        "language_codes": ["fa"],
        "priority": 16,
    },
    {
        "username": "@HiVPN_VPNBOT",
        "title": "HiVPN Store",
        "category": "vpn",
        "tags": ["vpn"],
        "language_codes": ["fa", "en"],
        "monthly_users": 25306,
        "priority": 17,
    },
    {
        "username": "@SmartVPNrobot",
        "title": "خرید فیلترشکن کانفیگ شکن",
        "category": "vpn",
        "tags": ["vpn", "proxy"],
        "language_codes": ["fa"],
        "priority": 15,
    },
    {
        "username": "@ArV2rayvip_bot",
        "title": "ArV2rayVip",
        "category": "vpn",
        "tags": ["vpn", "v2ray"],
        "language_codes": ["fa"],
        "monthly_users": 10945,
        "priority": 16,
    },
    {
        "username": "@omdekaribot",
        "title": "Forosh Hamkari VPN",
        "category": "vpn",
        "tags": ["vpn"],
        "language_codes": ["fa"],
        "priority": 12,
    },
    {
        "username": "@UltraWallet_bot",
        "title": "Ultra Wallet",
        "category": "wallet",
        "tags": ["wallet"],
        "language_codes": ["fa", "en"],
        "monthly_users": 15537,
        "priority": 14,
    },
    {
        "username": "@melobot",
        "title": "melobot",
        "category": "music",
        "tags": ["music"],
        "language_codes": ["fa"],
        "monthly_users": 922140,
        "priority": 10,
    },
    {
        "username": "@APKCLUB_DownloaderBot",
        "title": "APKCLUB Downloader",
        "category": "download",
        "tags": ["download", "apk"],
        "language_codes": ["fa", "en"],
        "monthly_users": 59998,
        "priority": 10,
    },
]


def upsert_default_bot_catalog(*, related_within_category: bool = True) -> dict[str, int]:
    """Idempotent upsert of curated catalog rows. Returns created/updated counts."""
    from apps.telegram_ads.models import TargetBotCatalogEntry
    from apps.telegram_ads.services.bot_recommendation import normalize_catalog_username

    by_category: dict[str, list[str]] = {}
    created = updated = 0
    for row in DEFAULT_BOT_CATALOG:
        at = normalize_catalog_username(str(row["username"]))
        if not at:
            continue
        category = str(row.get("category") or "").strip().casefold()
        if category:
            by_category.setdefault(category, []).append(at)
        defaults = {
            "title": str(row.get("title") or at.lstrip("@"))[:200],
            "photo_url": str(row.get("photo_url") or "")[:500],
            "category": category,
            "language_codes": list(row.get("language_codes") or []),
            "topic_ids": list(row.get("topic_ids") or []),
            "tags": list(row.get("tags") or []),
            "related_usernames": list(row.get("related_usernames") or []),
            "monthly_users": row.get("monthly_users"),
            "priority": int(row.get("priority") or 0),
            "is_active": True,
        }
        if defaults["monthly_users"] is not None:
            try:
                defaults["monthly_users"] = int(defaults["monthly_users"])
                if defaults["monthly_users"] <= 0:
                    defaults["monthly_users"] = None
            except (TypeError, ValueError):
                defaults["monthly_users"] = None
        obj, was_created = TargetBotCatalogEntry.objects.update_or_create(
            username=at,
            defaults=defaults,
        )
        if was_created:
            created += 1
        else:
            updated += 1
            _ = obj

    if related_within_category:
        for category, usernames in by_category.items():
            for at in usernames:
                peers = [u for u in usernames if u.casefold() != at.casefold()]
                TargetBotCatalogEntry.objects.filter(username=at).update(related_usernames=peers[:24])

    return {"created": created, "updated": updated, "total": created + updated}
