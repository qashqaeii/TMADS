from unittest.mock import patch
import pytest
from django.urls import reverse
from apps.accounts.models import User
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError

def test_ads_pagination(monkeypatch):
    class Api:
        def get_ads_list(self,*,offset,limit):
            return {"ads":[{"ad_id":1 if offset is None else 2}],"total_count":2,**({"next_offset":"next"} if offset is None else {})}
    client=TelegramAdsClient()
    monkeypatch.setattr(client,"_run",lambda name,fn:fn(Api()))
    assert [ad["ad_id"] for ad in client.list_advertisements()]==[1,2]

@pytest.mark.django_db
def test_account_report_access(client,customer_user):
    url=reverse("operations:telegram_account")+"?section=report&load=1&period=2026-11"
    client.force_login(customer_user)
    with patch("apps.operations.account_reports.TelegramAdsClient") as api:
        assert client.get(url).status_code==403
        api.assert_not_called()
    admin=User.objects.create_user(username="account-admin",role=User.Role.ADMIN)
    client.force_login(admin)
    with patch("apps.operations.account_reports.TelegramAdsClient") as api:
        api.return_value.get_account_report.return_value=[{"ad_id":1,"ad_title":"report example","views":50,"currency":"XTR","spent_budget":10}]
        response=client.get(url)
        assert response.status_code==200
        assert b"report example" in response.content
        assert "استار تلگرام".encode() in response.content
        assert b"XTR" not in response.content
        assert "از ۱۰ آبان تا ۹ آذر ۱۴۰۵".encode() in response.content
        api.return_value.get_account_report.assert_called_once_with(2026, 11)
