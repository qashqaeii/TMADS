from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.campaigns.models import Campaign, CampaignStatusHistory, TelegramAdvertisement
from apps.finance.models import AccountFundingTransfer, AdvertisingOrder
from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError, TelegramAdsWriteDisabled
from apps.telegram_ads.services.ad_write import ExecutionMode, execute_create_ad
from apps.telegram_ads.services.submission_guard import require_submission_order
from apps.telegram_ads.services.account_connections import campaign_account_snapshot, campaign_client

logger = logging.getLogger(__name__)


def _is_customer_owned(campaign):
    connection = getattr(campaign, "telegram_connection", None)
    return bool(connection and connection.connection_type == "customer_owned")


def _validate_targets_and_catalog(campaign, client):
    if campaign.target_type == Campaign.TargetType.BOTS:
        from apps.telegram_ads.services.bot_eligibility import validate_bot_targets
        targeting = getattr(campaign, "targeting", None)
        bot_ids = (targeting.config if targeting else {}).get("bot_ids") or []
        errors = validate_bot_targets(bot_ids, strict=True, require_verified=True)
        if errors or not bot_ids:
            raise ValueError("؛ ".join(errors) or "ربات هدف تأیید نشده است.")
    from apps.telegram_ads.services.catalog_verification import require_verified_catalog
    require_verified_catalog(campaign, client)


def _claim_customer_owned_submission(campaign_id):
    """Claim a direct customer-owned submission without creating a TMADS order."""
    from apps.policies.services.preflight import assert_submission_ready

    with transaction.atomic():
        campaign = Campaign.objects.select_for_update(of=("self",)).select_related(
            "telegram_connection", "telegram_connection__related_account",
        ).get(pk=campaign_id)
        if campaign.status != Campaign.Status.READY_FOR_SUBMISSION:
            raise ValueError("کمپین در وضعیت مجاز ثبت مستقیم نیست.")
        if campaign.remote_ads.exclude(remote_ad_id="").exists():
            raise ValueError("این کمپین قبلاً به تبلیغ تلگرام متصل شده است.")
        if not campaign.telegram_connection_id or not _is_customer_owned(campaign):
            raise ValueError("اتصال اختصاصی مشتری برای این کمپین ثبت نشده است.")
        if not getattr(settings, "TELEGRAM_ADS_CUSTOMER_OWNED_ENABLED", False):
            raise TelegramAdsWriteDisabled("مدیریت حساب اختصاصی مشتری در تنظیمات پلتفرم غیرفعال است.")
        if campaign.customer.is_suspended:
            raise ValueError("حساب مشتری غیرفعال است.")
        if AdvertisingOrder.objects.filter(campaign_id=campaign.pk).exists():
            raise ValueError("حساب اختصاصی مشتری نباید سفارش یا رزرو کیف پول TMADS داشته باشد.")
        if campaign.budget_irr or campaign.daily_cap_irr:
            raise ValueError("بودجه مستقیم نباید از مسیر ریالی یا کیف پول TMADS ثبت شود.")
        amount = Decimal(str(campaign.account_budget_amount))
        daily = Decimal(str(campaign.account_daily_budget_limit))
        if not amount.is_finite() or amount <= 0 or not daily.is_finite() or daily < 0 or daily > amount:
            raise ValueError("بودجه حساب تلگرام یا سقف روزانه معتبر نیست.")
        if campaign.budget_currency != campaign.telegram_connection.currency:
            raise ValueError("ارز بودجه با ارز حساب متصل مطابقت ندارد.")
        assert_submission_ready(campaign, check_operator=False)
        client = campaign_client(campaign)
        _validate_targets_and_catalog(campaign, client)
        account = campaign_account_snapshot(campaign)
        if account["currency"] != campaign.budget_currency:
            raise ValueError("ارز حساب تلگرام تغییر کرده است؛ بودجه را دوباره بررسی کنید.")
        if account["remaining_budget"] < amount:
            raise ValueError(
                f"موجودی حساب تلگرام کافی نیست؛ موجودی فعلی {account['remaining_budget']} {account['currency']} است."
            )
        campaign.status = Campaign.Status.SUBMITTING
        campaign.save(update_fields=["status", "updated_at"])
        CampaignStatusHistory.objects.create(
            campaign=campaign,
            from_status=Campaign.Status.READY_FOR_SUBMISSION,
            to_status=Campaign.Status.SUBMITTING,
            note="ثبت مستقیم با حساب و موجودی متعلق به مشتری؛ بدون کیف پول یا سفارش TMADS",
        )
        return campaign


def _claim_submission(campaign_id):
    """Claim a platform-managed or legacy wallet-funded submission."""
    from apps.policies.services.preflight import assert_submission_ready

    with transaction.atomic():
        campaign = Campaign.objects.select_for_update(of=("self",)).select_related(
            "telegram_connection", "telegram_connection__related_account",
        ).get(pk=campaign_id)
        order = require_submission_order(campaign, lock=True)
        from apps.operations.review import require_recorded_approval
        require_recorded_approval(campaign)
        assert_submission_ready(campaign, check_operator=True)
        client = campaign_client(campaign)
        _validate_targets_and_catalog(campaign, client)

        if campaign.telegram_connection_id:
            connection = campaign.telegram_connection
            if connection.connection_type != "platform_managed":
                raise ValueError("مدل مالی سفارش با نوع حساب انتخاب‌شده سازگار نیست.")
            related = connection.related_account
            if (
                not related or related.status != "provisioned"
                or related.remote_account_id != connection.remote_account_id
            ):
                raise ValueError("حساب مرتبط مشتری تأیید نشده است.")
            central = TelegramAdsClient().get_account()
            child = campaign_account_snapshot(campaign)
            try:
                central_balance = Decimal(str(central["remaining_budget"]))
                if (
                    str(central.get("account_id") or "") != related.main_account_id
                    or central.get("currency") != "TON"
                    or child["currency"] != "TON"
                    or not central_balance.is_finite()
                    or central_balance < order.ton_allocation
                ):
                    raise ValueError("موجودی حساب مرکزی یا هویت حساب مرتبط برای تأمین اعتبار معتبر نیست.")
            except (InvalidOperation, TypeError, KeyError):
                raise ValueError("موجودی حساب مرکزی قابل تأیید نیست.") from None
        else:
            account = TelegramAdsClient().get_account()
            try:
                remaining = Decimal(str(account["remaining_budget"]))
                if account.get("currency") != "TON" or not remaining.is_finite() or remaining < order.ton_allocation:
                    raise ValueError("ارز یا موجودی حساب مرکزی برای سفارش معتبر نیست.")
            except (InvalidOperation, TypeError, KeyError):
                raise ValueError("موجودی حساب مرکزی قابل تأیید نیست.") from None

        campaign.status = Campaign.Status.SUBMITTING
        campaign.save(update_fields=["status", "updated_at"])
        order.status = AdvertisingOrder.Status.SUBMITTING
        order.save(update_fields=["status", "updated_at"])
        CampaignStatusHistory.objects.create(
            campaign=campaign, from_status=Campaign.Status.READY_FOR_SUBMISSION,
            to_status=campaign.status, note="ارسال در جریان؛ کلید یکتای ثابت",
        )
        return campaign, order.id


def _fund_platform_managed_account(campaign, order):
    from apps.finance.account_funding import fund_platform_managed_transfer

    return fund_platform_managed_transfer(
        campaign,
        amount=order.ton_allocation,
        idempotency_key=f"tmads-fund-{order.pk}",
        order=order,
    )


def submit_campaign_to_telegram(campaign: Campaign) -> TelegramAdvertisement:
    """Submit through the account selected on the campaign, without cross-account fallback."""
    if not settings.TELEGRAM_ADS_WRITE_ENABLED or not settings.TELEGRAM_ADS_PAID_SUBMISSION_ENABLED:
        raise TelegramAdsWriteDisabled("ارسال زنده غیرفعال است.")

    direct = _is_customer_owned(campaign)
    if direct:
        campaign = _claim_customer_owned_submission(campaign.pk)
        order_id = None
    else:
        campaign, order_id = _claim_submission(campaign.pk)

    try:
        if order_id:
            order = AdvertisingOrder.objects.get(pk=order_id)
            _fund_platform_managed_account(campaign, order)
        execute_create_ad(campaign, mode=ExecutionMode.LIVE)
        with transaction.atomic():
            current = Campaign.objects.select_for_update(of=("self",)).select_related("telegram_connection").get(pk=campaign.pk)
            ad = TelegramAdvertisement.objects.get(campaign=current)
            if not ad.remote_ad_id:
                raise TelegramAdsError("شناسه تبلیغ برای تطبیق موجود نیست.")
            current.status = Campaign.Status.AWAITING_TELEGRAM
            current.save(update_fields=["status", "updated_at"])
            if order_id:
                order = AdvertisingOrder.objects.select_for_update().get(pk=order_id)
                order.status = AdvertisingOrder.Status.SUBMITTING
                order.save(update_fields=["status", "updated_at"])
            CampaignStatusHistory.objects.create(
                campaign=current, from_status=Campaign.Status.SUBMITTING,
                to_status=current.status,
                note=(
                    "تبلیغ از حساب اختصاصی مشتری ایجاد شد؛ هیچ مبلغی از کیف پول TMADS برداشت نشد."
                    if direct else
                    "شناسه تبلیغ از حساب مرتبط تلگرام دریافت شد؛ تسویه مالی در انتظار تطبیق"
                ),
            )
            return ad
    except Exception as exc:
        logger.warning("submission requires reconciliation for campaign=%s (%s)", campaign.pk, type(exc).__name__)
        with transaction.atomic():
            current = Campaign.objects.select_for_update().get(pk=campaign.pk)
            current.status = Campaign.Status.RECONCILIATION
            current.save(update_fields=["status", "updated_at"])
            CampaignStatusHistory.objects.create(
                campaign=current, from_status=Campaign.Status.SUBMITTING,
                to_status=current.status, note="نتیجه ارسال نامطمئن؛ ارسال مجدد ممنوع تا تطبیق",
            )
        raise TelegramAdsError("نتیجه ارسال نیازمند تطبیق است. برای جلوگیری از ایجاد تبلیغ تکراری، دوباره ارسال نکنید.") from exc
