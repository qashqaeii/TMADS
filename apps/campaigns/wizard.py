"""Legacy wizard constants — studio logic lives in studio.py."""

from apps.campaigns.studio import STUDIO_STEPS, validate_studio_step

# Backward compatibility for imports / old tests
WIZARD_STEPS = STUDIO_STEPS + [("payment", "پرداخت")]  # payment handled inside step 5 UI

SUPPORTED_OBJECTIVES = {"bot", "channel", "mini_app"}
SUPPORTED_PLACEMENTS = {"search_result", "bot_banner", "channel_post", "video_banner", "channels", "video"}


def validate_step(campaign, step: int, data: dict) -> list[str]:
    if getattr(campaign, "wizard_version", 1) >= 2:
        return validate_studio_step(campaign, step, data, strict=False)
    return _legacy_validate_step(campaign, step, data)


def _legacy_validate_step(campaign, step: int, data: dict) -> list[str]:
    errors: list[str] = []
    if step == 1:
        obj = data.get("objective")
        if obj and obj not in SUPPORTED_OBJECTIVES:
            errors.append("نوع مقصد انتخاب‌شده هنوز پشتیبانی نمی‌شود.")
    if step == 2:
        dest = (data.get("destination") or "").strip()
        if dest and len(dest) < 3:
            errors.append("مقصد تبلیغ را وارد کنید.")
    if step == 3:
        pl = data.get("placement")
        if pl and pl not in SUPPORTED_PLACEMENTS:
            errors.append("جایگاه نمایش با API سازگار نیست.")
    if step == 5:
        text = (data.get("ad_text") or "").strip()
        if text and len(text) < 5:
            errors.append("متن تبلیغ خیلی کوتاه است.")
        if len(text) > 160:
            errors.append("متن تبلیغ بیش از حد مجاز است.")
    if step == 6:
        from apps.campaigns.studio import parse_studio_int_amount
        from apps.core.dates import to_persian_digits
        from apps.finance.services.money import (
            irr_to_toman_int,
            minimum_advertising_budget_irr,
            toman_to_irr,
        )

        try:
            budget_toman = parse_studio_int_amount(data.get("budget_toman"))
        except ValueError:
            budget_toman = 0
        min_irr = minimum_advertising_budget_irr()
        if budget_toman and min_irr and toman_to_irr(budget_toman) < min_irr:
            min_fa = to_persian_digits(f"{irr_to_toman_int(min_irr):,}".replace(",", "٬"))
            errors.append(f"حداقل بودجه معادل ۱ گرام است (حدود {min_fa} تومان با نرخ روز).")
    return errors
