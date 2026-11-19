import pytest
from unittest.mock import patch
from apps.accounts.models import User
from apps.telegram_ads.services.related_accounts import request_account,execute_account
from apps.telegram_ads.models import RelatedAccountRequest

@pytest.mark.django_db
def test_account_requires_consent_and_never_executes_when_disabled(customer_user,settings):
    data={"title":"Example", "full_name":"Example Company","email":"info@example.invalid","phone_number":"+49123456789","country":"Germany","city":"Berlin"}
    with pytest.raises(ValueError):
        request_account(customer_user,data)
    row=request_account(customer_user,{**data,"consent":"on"})
    with pytest.raises(ValueError):
        request_account(customer_user,{**data,"consent":"on"})
    manager=User.objects.create_user(username="related-admin",role=User.Role.ADMIN)
    settings.TELEGRAM_ADS_RELATED_ACCOUNTS_ENABLED=False
    with patch("apps.telegram_ads.services.related_accounts.TelegramAdsClient") as api:
        with pytest.raises(ValueError):
            execute_account(row.pk,manager)
        api.assert_not_called()
    assert RelatedAccountRequest.objects.get(pk=row.pk).status=="pending"
