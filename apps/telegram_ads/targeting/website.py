"""API website destination fields; capability gate remains default-off."""
from urllib.parse import urlparse
from django.conf import settings
from apps.telegram_ads.targeting.normalize import safe_destination_link

WEBSITE_BUTTONS = [
    ("","باز کردن وب‌سایت"),("subscribe","اشتراک"),("view","مشاهده"),("read","مطالعه"),
    ("learn_more","اطلاعات بیشتر"),("download","دانلود"),("open","باز کردن"),
    ("sign_up","ثبت‌نام"),("buy","خرید"),("order","سفارش"),("play","بازی"),
    ("try","امتحان کردن"),("leave_request","ثبت درخواست"),
]

def is_external(url):
    try:
        parsed=urlparse(url or "")
        return parsed.scheme in {"http","https"} and parsed.hostname not in {"t.me","telegram.me","www.t.me","www.telegram.me"}
    except ValueError:
        return False

def website_fields(destination,data):
    if not is_external(destination):
        return {}
    return {"website_name":str(data.get("website_name") or "").strip(),
            "button":str(data.get("button") or "").strip()}

def validate_website_fields(destination,values,*,strict):
    if not is_external(destination):
        return []
    errors=[]
    if not safe_destination_link(destination) or not destination.startswith("https://"):
        errors.append("مقصد وب‌سایت باید آدرس HTTPS معتبر باشد.")
    name=values.get("website_name") or ""
    if len(name)>40 or strict and not name:
        errors.append("نام وب‌سایت باید بین ۱ تا ۴۰ کاراکتر باشد.")
    if values.get("button","") not in dict(WEBSITE_BUTTONS):
        errors.append("نوع دکمه وب‌سایت معتبر نیست.")
    return errors

def website_submission_errors(destination,values):
    errors=validate_website_fields(destination,values,strict=True)
    if is_external(destination) and not getattr(settings,"TELEGRAM_ADS_WEBSITE_ENABLED",False):
        errors.append("ارسال تبلیغ با مقصد وب‌سایت هنوز برای حساب فعال نشده است.")
    if values.get("website_photo_id") or values.get("conversion_event_id"):
        errors.append("مالکیت تصویر وب‌سایت یا رویداد تبدیل در حساب تبلیغاتی هنوز تأیید نشده است.")
    return errors
