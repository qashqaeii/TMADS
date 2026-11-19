import json
from django.http import QueryDict
from apps.campaigns.studio import parse_targeting_payload
from apps.campaigns.schedule_utils import parse_schedule_payload
from apps.telegram_ads.targeting.website import website_fields,website_submission_errors

def test_user_channel_audiences_and_intersection():
    data=QueryDict("channel_ids=%40vote%0A%40gif&exclude_channel_ids=%40other&intersect_topics=1")
    cfg=parse_targeting_payload(data,"users")
    assert cfg["channel_ids"]==["@vote","@gif"]
    assert cfg["exclude_channel_ids"]==["@other"]
    assert cfg["intersect_topics"] is True

def test_utc_schedule_is_not_replaced():
    data={"schedule_enabled":"1","schedule_json":json.dumps({"week_hours_mask":[1]*7}),"schedule_timezone":"0"}
    assert parse_schedule_payload(data)["timezone"]==0

def test_external_website_gated(settings):
    settings.TELEGRAM_ADS_WEBSITE_ENABLED=False
    values=website_fields("https://example.com",{"website_name":"Example","button":"buy"})
    assert values=={"website_name":"Example","button":"buy"}
    assert website_submission_errors("https://example.com",values)
    assert website_fields("https://t.me/vote",values)=={}
