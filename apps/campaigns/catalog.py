"""Read-only catalog. Only server-returned IDs are offered as verified selections."""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from django.conf import settings
from django.core.cache import cache

from apps.telegram_ads.client import TelegramAdsClient
from apps.telegram_ads.exceptions import TelegramAdsError
from apps.telegram_ads.services.bot_eligibility import BotEligibilityResult, check_bot_eligibility
from apps.telegram_ads.targeting.normalize import parse_bot_peer_input

logger = logging.getLogger(__name__)
CACHE_TTL = 3600
COUNTRY_FA = {"IR":"ایران", "DE":"آلمان", "US":"ایالات متحده", "GB":"بریتانیا",
              "TR":"ترکیه", "AE":"امارات", "FR":"فرانسه"}
# These are standard codes, not proof that this account supports them.
FALLBACK_COUNTRIES = [
    {"country_code": code, "name": name, "name_fa": COUNTRY_FA[code], "verified": False}
    for code, name in (("IR","Iran"), ("DE","Germany"), ("US","United States"))
]
# فهرست استاندارد IETF مطابق ads.telegram.org (برای آفلاین؛ verified=False).
FALLBACK_LANGUAGES = [
    {"language_code": code, "name": name, "verified": False}
    for code, name in (
        ("en", "English"), ("af", "Afrikaans"), ("sq", "Albanian"), ("am", "Amharic"),
        ("ar", "Arabic"), ("hy", "Armenian"), ("az", "Azerbaijani"), ("eu", "Basque"),
        ("be", "Belarusian"), ("bn", "Bengali"), ("bg", "Bulgarian"), ("my", "Burmese"),
        ("ca", "Catalan"), ("zh-Hans", "Chinese (Simplified)"), ("zh-Hant", "Chinese (Traditional)"),
        ("hr", "Croatian"), ("cs", "Czech"), ("da", "Danish"), ("nl", "Dutch"),
        ("eo", "Esperanto"), ("et", "Estonian"), ("fil", "Filipino"), ("fi", "Finnish"),
        ("fr", "French"), ("gl", "Galician"), ("ka", "Georgian"), ("de", "German"),
        ("el", "Greek"), ("gu", "Gujarati"), ("he", "Hebrew"), ("hi", "Hindi"),
        ("hu", "Hungarian"), ("id", "Indonesian"), ("ga", "Irish"), ("it", "Italian"),
        ("ja", "Japanese"), ("kn", "Kannada"), ("kk", "Kazakh"), ("km", "Khmer"),
        ("ko", "Korean"), ("lv", "Latvian"), ("lt", "Lithuanian"), ("ms", "Malay"),
        ("ml", "Malayalam"), ("mt", "Maltese"), ("mr", "Marathi"), ("ne", "Nepali"),
        ("nb", "Norwegian (Bokmål)"), ("or", "Odia"), ("fa", "Persian"), ("pl", "Polish"),
        ("pt-BR", "Portuguese (Brazil)"), ("pt-PT", "Portuguese (Portugal)"),
        ("ro", "Romanian"), ("ru", "Russian"), ("sr", "Serbian"), ("sk", "Slovak"),
        ("sl", "Slovene"), ("es", "Spanish"), ("sw", "Swahili"), ("sv", "Swedish"),
        ("tg", "Tajik"), ("ta", "Tamil"), ("te", "Telugu"), ("th", "Thai"),
        ("tr", "Turkish"), ("tk", "Turkmen"), ("uk", "Ukrainian"), ("ur", "Urdu"),
        ("uz", "Uzbek"), ("vi", "Vietnamese"),
    )
]
LANGUAGE_NAME_FA = {"fa": "فارسی", "en": "انگلیسی", "ar": "عربی", "ru": "روسی", "tr": "ترکی"}
# برچسب فارسی موضوعات رسمی ads.telegram.org (شناسه از getTargetTopicsList).
TOPIC_NAME_FA = {
    1: "هنر و طراحی",
    2: "شرط‌بندی و قمار",
    3: "کتاب",
    4: "کسب‌وکار و کارآفرینی",
    5: "خودرو و وسایل نقلیه",
    6: "سلبریتی و سبک زندگی",
    7: "رمزارزها",
    8: "فرهنگ و رویدادها",
    9: "حقایق جالب",
    10: "فهرست کانال‌ها و ربات‌ها",
    12: "اقتصاد و مالی",
    13: "آموزش",
    15: "مد و زیبایی",
    16: "تناسب اندام",
    18: "غذا و آشپزی",
    19: "یادگیری زبان خارجی",
    21: "سلامت و پزشکی",
    22: "تاریخ",
    23: "سرگرمی و فعالیت‌ها",
    24: "خانه و معماری",
    25: "طنز و میم",
    26: "سرمایه‌گذاری",
    27: "فرصت‌های شغلی",
    28: "کودک و فرزندپروری",
    29: "بازاریابی و روابط عمومی",
    30: "انگیزه و خودسازی",
    31: "فیلم",
    32: "موسیقی",
    33: "پیشنهادها و تخفیف‌ها",
    35: "حیوانات خانگی",
    37: "سیاست و حوادث",
    39: "روان‌شناسی و روابط",
    40: "املاک",
    41: "تفریح و سرگرمی",
    42: "دین و معنویت",
    43: "علم",
    45: "ورزش",
    46: "فناوری و اینترنت",
    47: "سفر و گردشگری",
    48: "بازی‌های ویدیویی",
    63: "سایر",
}


def _key(kind):
    scope = hashlib.sha256(settings.TELEGRAM_ADS_API_TOKEN.encode()).hexdigest()[:16]
    return f"tmads:catalog:v4:{scope}:{kind}"


def _catalog(kind, loader, normalize, fallback):
    key = _key(kind)
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        rows = []
        for item in loader(TelegramAdsClient()):
            row = normalize(item)
            if row:
                rows.append({**row, "verified": True})
        cache.set(key, rows, CACHE_TTL)
        return rows
    except Exception as exc:
        logger.warning("catalog %s unavailable: %s", kind, type(exc).__name__)
        return [dict(item) for item in fallback]


def _country_row(item):
    code = str(item.get("country_code") or "").upper()
    if not re.fullmatch(r"[A-Z]{2}", code):
        return None
    name = item.get("name") or code
    return {"country_code":code, "name":name, "name_fa":COUNTRY_FA.get(code, name)}


def _language_row(item):
    code = str(item.get("language_code") or "")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,35}", code):
        return None
    name = item.get("name") or code
    row = {"language_code": code, "name": name}
    if code in LANGUAGE_NAME_FA:
        row["name_fa"] = LANGUAGE_NAME_FA[code]
    return row


def _topic_row(item):
    tid = item.get("topic_id")
    if type(tid) is not int or tid <= 0:
        return None
    name = item.get("name") or str(tid)
    row = {"topic_id": tid, "name": name}
    if tid in TOPIC_NAME_FA:
        row["name_fa"] = TOPIC_NAME_FA[tid]
    return row


def get_countries():
    return _catalog("countries", lambda c:c.get_target_countries(), _country_row, FALLBACK_COUNTRIES)


def get_languages():
    return _catalog("languages", lambda c:c.get_target_languages(), _language_row, FALLBACK_LANGUAGES)


def get_topics():
    return _catalog("topics", lambda c:c.get_target_topics(), _topic_row, [])


def search_locations(country_code: str, query: str, *, limit: int = 20, raise_on_unavailable=False):
    country_code = (country_code or "").strip().upper()
    query = (query or "").strip()
    if not re.fullmatch(r"[A-Z]{2}", country_code) or not 2 <= len(query) <= 100:
        return []
    limit = max(1, min(int(limit), 20))
    key = _key(f"location:{country_code}:{hashlib.sha256(query.casefold().encode()).hexdigest()}:{limit}")
    cached = cache.get(key)
    if cached is not None:
        return cached
    try:
        payload = TelegramAdsClient().get_target_locations(country_code, query, limit=limit)
        locations = payload.get("locations") or []
        rows = []
        for loc in locations:
            lid = loc.get("location_id")
            code = str(loc.get("country_code") or country_code).upper()
            if type(lid) is int and lid > 0 and code == country_code:
                rows.append({"location_id":lid, "name":loc.get("name") or str(lid),
                             "region":loc.get("region") or "", "country_code":code, "verified":True})
        cache.set(key, rows, 600)
        return rows
    except Exception as exc:
        logger.warning("location catalog unavailable: %s", type(exc).__name__)
        if raise_on_unavailable:
            raise TelegramAdsError("فهرست موقعیت‌ها در حال حاضر در دسترس نیست.") from None
        return []


def resolve_bot(username: str) -> dict[str, Any]:
    try:
        result: BotEligibilityResult = check_bot_eligibility(username)
        return result.to_json()
    except Exception:
        logger.exception("resolve_bot programming error")
        return {
            "ok": False,
            "query": (username or "").strip(),
            "eligibility": "api_unavailable",
            "message_fa": "بررسی ربات در حال حاضر امکان‌پذیر نیست.",
            "hard_block": False,
            "verified": False,
            "error": "internal",
        }


def resolve_channel(username: str):
    at, _ = parse_bot_peer_input(username)
    if not at:
        return {"ok":False, "error":"نام کاربری کانال معتبر نیست.", "pending":False}
    try:
        data = TelegramAdsClient().resolve_target_channel(at)
        if type(data.get("channel_id")) is not int or data["channel_id"] == 0:
            return {"ok":False, "pending":True, "error":"کانال هنوز تأیید نشده است."}
        return {"ok":True, "channel":data}
    except TelegramAdsError:
        return {"ok":False, "pending":True, "error":"بررسی کانال در حال حاضر ممکن نیست."}
