"""Do not invent uplift or compare incomparable campaigns."""
from decimal import Decimal
import pytest
from apps.campaigns.models import Campaign, TelegramAdvertisement
from apps.campaigns.performance_advice import campaign_advice


@pytest.mark.django_db
def test_advice_requires_real_and_current_remote_metrics(customer_user):
    campaign=Campaign.objects.create(customer=customer_user.customer_profile,
        status=Campaign.Status.ACTIVE)
    metrics={"has_stats":True,"has_ctr":True,"impressions":2500,"ctr":0.3}
    assert campaign_advice(campaign,metrics)==[]
    TelegramAdvertisement.objects.create(campaign=campaign,remote_ad_id="200")
    assert any("متن" in x["title"] for x in campaign_advice(campaign,metrics))
    stale={**metrics,"stats_stale":True}
    result=campaign_advice(campaign,stale)
    assert len(result)==1
    assert "به‌روز" in result[0]["title"]


@pytest.mark.django_db
def test_no_false_conversion_advice_when_action_type_missing(customer_user):
    campaign=Campaign.objects.create(customer=customer_user.customer_profile,
        status=Campaign.Status.ACTIVE)
    TelegramAdvertisement.objects.create(campaign=campaign,remote_ad_id="201")
    metrics={"has_stats":True,"has_actions":True,"has_clicks":True,
        "clicks":100,"actions":0,"action_type":"","has_ctr":False,
        "currency":"TON","spent_ton":Decimal("9.50"),"remaining_ton":Decimal("0.50")}
    result=campaign_advice(campaign,metrics)
    assert not any(x["title"]=="کنترل مسیر تبدیل" for x in result)
    assert any(x["title"]=="مانده بودجه کم است" for x in result)
