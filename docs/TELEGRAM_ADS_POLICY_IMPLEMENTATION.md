# Telegram Ads Policy Implementation (TMADS)

## معماری

```text
apps/policies/
  models.py           # PolicyVersion, Evaluation, Finding, Acceptance, Operator gate
  services/
    engine.py         # evaluate_campaign()
    preflight.py      # CampaignPolicyPreflight
    text_rules.py
    destination_rules.py
    targeting_rules.py
    content_rules.py  # advisory prohibited hints
    policy_versions.py
  views.py            # /app/ad-policies/
```

## نقاط اتصال

| مرحله | رفتار |
|-------|--------|
| ویزارد | `evaluate_campaign(strict=False)` + پنل `policy_panel` |
| پرداخت | `CampaignPolicyPreflight(strict=True)` + `record_acceptance` |
| Ops تأیید | preflight بدون درگاه اپراتور؛ BLOCKED مانع تأیید |
| ارسال Telegram | `assert_submission_ready()` + درگاه اپراتور APPROVED |

## نسخه‌گذاری

- `PolicyVersion` ردیف فعال در DB؛ کد پیش‌فرض `CURRENT_POLICY_VERSION` در `constants.py`.
- نتایج تاریخی در `CampaignPolicyEvaluation` حفظ می‌شوند.

## ممیزی مالی (فاز ۱۳)

- **Telegram ToS §4.3:** اعتبار تلگرام اپراتور قابل برداشت/انتقال/refund از طرف تلگرام نیست.
- **TMADS:** بازپرداخت مشتری طبق `docs/legal/refund.md` و وضعیت `RefundRequest` — منطق ledger موجود تغییر نکرده است.
- ویزارد مرحله بودجه پیام INFO از `financial_disclosures.py` نمایش می‌دهد.

## وابستگی‌های تولید

1. ثبت `OperatorAdvertisingAuthorization` با `state=approved` پس از بررسی حقوقی §3.3(e).
2. بازبینی Ops هنگام به‌روزرسانی رسمی Guidelines.
3. عدم فعال‌سازی `TELEGRAM_ADS_WRITE_ENABLED` بدون gate تأیید‌شده.
