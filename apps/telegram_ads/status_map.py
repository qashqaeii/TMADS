from apps.campaigns.models import Campaign


def map_remote_status_to_campaign(item: dict) -> str:
    remote = str(item.get("status") or "").lower()
    if item.get("is_paused") and remote == "active":
        return Campaign.Status.PAUSED
    mapping = {
        "active": Campaign.Status.ACTIVE,
        "stopped": Campaign.Status.PAUSED,
        "on_hold": Campaign.Status.PAUSED,
        "declined": Campaign.Status.REJECTED,
        "in_review": Campaign.Status.AWAITING_TELEGRAM,
        "ready_for_review": Campaign.Status.PENDING_REVIEW,
    }
    return mapping.get(remote, Campaign.Status.ACTIVE if remote == "active" else Campaign.Status.PAUSED)
