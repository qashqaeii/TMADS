# FarazSMS / TMADS
Implemented independently of Divarfiling credentials. Uses the existing Divarfiling REST pattern and the official contract: https://docs.iranpayamak.com/send-pattern-based-sms-13925177e0

## Configuration
Set in the TMADS deployment environment only, not in Git and not via a web form:
- SMS_PROVIDER=faraz
- SMS_ENABLED=true (only after checking the appropriate approved patterns)
- FARAZSMS_API_KEY, FARAZSMS_LINE_NUMBER
- FARAZSMS_OTP_LINE_NUMBER (optional dedicated line)
- FARAZSMS_OTP_ATTR=code
- FARAZSMS_PATTERN_VERIFY_MOBILE, FARAZSMS_PATTERN_WALLET_CREDIT, FARAZSMS_PATTERN_BUDGET_LOW, FARAZSMS_PATTERN_CAMPAIGN_STATUS

## Suggested pattern text (submit to Faraz for approval)
- verify_mobile: «تی‌ام‌ادز؛ کد تأیید شماره موبایل: %code% — اعتبار ۵ دقیقه. کد را در اختیار دیگران قرار ندهید.»
- wallet_credit: «تی‌ام‌ادز؛ کیف پول شما به مبلغ %amount% تومان شارژ شد. رسید در داشبورد قابل مشاهده است.»
- budget_low: «تی‌ام‌ادز؛ بودجه یکی از تبلیغات شما رو به پایان است. وضعیت را در داشبورد بررسی کنید.» (no variables)
- campaign_status: «تی‌ام‌ادز؛ نتیجه بررسی کمپین شما: %status%. جزئیات را در داشبورد ببینید.»
Verify the exact placeholders and line restrictions in the actual provider panel. Campaign approval is internal review, not Telegram approval.

## Operations
Run Django migrations, Celery worker and beat. Worker dispatches pending messages on schedule. The operations SMS workspace is restricted to platform managers. Balance read is explicit; logs mask recipient numbers and distinguish provider acceptance from delivery. OTP codes are hashed and never stored in plaintext. OTP requests expire after five minutes, have a one-minute resend interval and a five-attempt cap. Existing email/password login remains independent. Customer mobile verification is required before receiving transactional SMS. Console mode cannot establish ownership.
A timeout can mean provider accepted the message. Unknown sends are never automatically repeated; review them in the provider panel. No bulk marketing or direct arbitrary sends.
## Live acceptance
Apply migrations and verify worker/beat, provider API key, approved patterns, line permissions, actual message delivery on an authorized test number, opt-out, and dashboard layout at mobile/desktop sizes. Mock tests do not verify actual delivery. No real SMS or account changes at Faraz have been made.
