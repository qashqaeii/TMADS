import pytest

from apps.campaigns.analytics import targeting_display_rows
from apps.campaigns.models import CampaignTargeting


@pytest.mark.django_db
def test_targeting_display_formats_imported_bots(customer_user):
    bots = [
        {"bot_id": 1, "title": "ربات تست", "username": "mybot", "photo_url": "https://t.me/x"},
        {"bot_id": 2, "title": "دیگر", "username": "otherbot"},
    ]
    targeting = CampaignTargeting(
        config={"api_target": {"bots": bots}},
    )
    rows = targeting_display_rows(targeting)
    bot_row = next(r for r in rows if r["label"] == "ربات‌ها")
    assert bot_row["kind"] == "chips"
    assert bot_row["count"] == 2
    copies = [i["copy"] for i in bot_row["items"]]
    assert "@mybot" in copies
    assert "photo_url" not in bot_row["copy_all"]
