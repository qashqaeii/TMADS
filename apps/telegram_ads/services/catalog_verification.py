"""Fresh read-only catalog verification immediately before a remote claim."""
from apps.campaigns.models import Campaign
from apps.telegram_ads.targeting.normalize import parse_bot_peer_input


def require_verified_catalog(campaign, client):
    if campaign.target_type not in {Campaign.TargetType.USERS, Campaign.TargetType.CHANNELS}:
        return
    targeting = getattr(campaign, "targeting", None)
    cfg = targeting.config if targeting else {}
    for fields, loader, identity, label in (
        (("country_codes",), client.get_target_countries, "country_code", "کشور"),
        (("language_codes",), client.get_target_languages, "language_code", "زبان"),
        (("topic_ids", "exclude_topic_ids"), client.get_target_topics, "topic_id", "موضوع"),
    ):
        selected = {str(v).casefold() for field in fields for v in (cfg.get(field) or [])}
        if not selected:
            continue
        known = {str(row[identity]).casefold() for row in loader() if identity in row}
        if not selected <= known:
            raise ValueError(f"حداقل یک {label} انتخاب‌شده توسط API تأیید نشد.")
    locations = cfg.get("location_ids") or []
    if locations:
        countries = cfg.get("country_codes") or []
        if len(countries) != 1:
            raise ValueError("شهرها باید متعلق به یک کشور انتخاب‌شده باشند.")
        ids = {int(x) for x in locations}
        rows = client.get_target_locations_by_ids(list(ids))
        valid = {int(row["location_id"]) for row in rows if row.get("country_code", "").upper() == countries[0].upper() and row.get("location_id")}
        if valid != ids:
            raise ValueError("شناسه یا کشور موقعیت انتخاب‌شده قابل تأیید نیست.")
    for field in ("channel_ids", "exclude_channel_ids"):
        for raw in cfg.get(field) or []:
            if type(raw) is int:
                peer = raw
            else:
                peer = parse_bot_peer_input(raw)[0]
            if not peer:
                raise ValueError("نام کاربری کانال معتبر نیست.")
            data = client.resolve_target_channel(peer, for_excluding=field == "exclude_channel_ids")
            if type(data.get("channel_id")) is not int or not data["channel_id"]:
                raise ValueError("حداقل یک کانال توسط API تأیید نشد.")
