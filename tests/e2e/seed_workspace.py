"""Only for disposable CI visual database; no external provider operations."""
import os
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.db import connection
from apps.accounts.models import User
from apps.campaigns.models import Campaign
from apps.finance.models import Wallet, WalletLedgerEntry, Invoice, AdvertisingOrder, RefundRequest, ExchangeRate
from apps.support.models import SupportTicket, SupportMessage
from apps.core.models import AuditLog
from apps.telegram_ads.models import APICapability, APIRequestLog

assert settings.APP_ENV == "LOCAL"
assert settings.PAYMENT_GATEWAY == "fake"
assert not settings.TELEGRAM_ADS_WRITE_ENABLED
assert not settings.TELEGRAM_ADS_API_TOKEN
assert not settings.SMS_ENABLED
assert connection.settings_dict["NAME"] == "tmads_visual"

customer = User.objects.create_user(
    username=os.environ["TMADS_E2E_USERNAME"], password=os.environ["TMADS_E2E_PASSWORD"],
    role=User.Role.CUSTOMER,
)
ops = User.objects.create_superuser(
    username=os.environ["TMADS_E2E_OPS_USERNAME"], password=os.environ["TMADS_E2E_OPS_PASSWORD"],
    email="operator@example.invalid", role=User.Role.ADMIN,
)
p = customer.customer_profile
p.display_name = "کسب‌وکار نمونه"
p.company_name = "گرام‌ادز آزمایشی"
p.save()
wallet, _ = Wallet.objects.get_or_create(customer=p)
wallet.available_irr = 5_000_000
wallet.reserved_irr = 1_500_000
wallet.save()
WalletLedgerEntry.objects.create(wallet=wallet, entry_type=WalletLedgerEntry.EntryType.DEPOSIT,
    amount_irr=6_500_000, balance_after_available=6_500_000, balance_after_reserved=0,
    idempotency_key="workspace-visual-ledger", description="داده آزمایشی")
draft = Campaign.objects.create(customer=p, name="کمپین معرفی محصول", status=Campaign.Status.DRAFT,
    destination="https://t.me/example", objective=Campaign.Objective.CHANNEL)
review = Campaign.objects.create(customer=p, name="کمپین توسعه مخاطبان", status=Campaign.Status.PENDING_REVIEW,
    destination="https://t.me/example", objective=Campaign.Objective.CHANNEL)
order = AdvertisingOrder.objects.create(customer=p, campaign_id=review.id, total_irr=1_500_000,
    status=AdvertisingOrder.Status.PAID)
Invoice.objects.create(customer=p, order=order, invoice_number="VISUAL-001", amount_irr=1_500_000,
    description="فاکتور نمونه برای تست رابط کاربری")
RefundRequest.objects.create(customer=p, order=order, amount_irr=500_000, reason="درخواست نمونه برای بررسی نمایشی")
ticket = SupportTicket.objects.create(customer=p, subject="راهنمای بررسی کمپین")
SupportMessage.objects.create(ticket=ticket, author=customer, body="برای بررسی وضعیت کمپین راهنمایی نیاز دارم.")
AuditLog.objects.create(actor=ops, action="visual.fixture", entity_type="Campaign", entity_id=draft.id)

# Read-only API health and rate fixtures; all data stays inside the disposable CI database.
APICapability.objects.update_or_create(
    feature_key="account_details",
    defaults={"state": APICapability.State.SUPPORTED,
              "details": {"reason": "دریافت اطلاعات حساب در محیط آزمایشی تأیید شد."},
              "last_checked_at": timezone.now()},
)
APICapability.objects.update_or_create(
    feature_key="campaign_create",
    defaults={"state": APICapability.State.PERMISSION_DENIED,
              "details": {"reason": "مجوز این قابلیت در محیط آزمایشی فعال نیست."},
              "last_checked_at": timezone.now()},
)
APIRequestLog.objects.create(operation="visual.account.read", success=True, meta={"source": "visual"})
APIRequestLog.objects.create(operation="visual.campaign.create", success=False, meta={"source": "visual"})
ExchangeRate.objects.create(
    ton_per_irr=Decimal("0.000000326170"),
    source="nobitex",
    is_active=True,
    details={
        "source": "nobitex",
        "irr_per_ton": 3065880,
        "best_ask_irr": "3065880",
        "best_bid_irr": "3060000",
        "last_trade_irr": "3063000",
        "market_symbol": "TONIRT",
        "stats_pair": "TONIRT",
        "fetched_at": timezone.now().isoformat(),
        "fetch_status": "ok",
        "is_fresh": True,
    },
)
