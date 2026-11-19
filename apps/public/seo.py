"""Public search metadata and a host-independent sitemap."""
import json

from urllib.parse import urlsplit, urlunsplit
from xml.etree import ElementTree as ET

from django.conf import settings
from django.http import HttpResponse, HttpResponseNotFound
from django.urls import reverse
from django.utils.safestring import mark_safe


PAGES = {
    "home": ("تبلیغات تلگرام | مدیریت Telegram Ads", "تی‌ام‌ادز، پلتفرم فارسی طراحی کمپین تبلیغات تلگرام، هدف‌گیری مخاطب، پیش‌فاکتور ریالی و گزارش عملکرد."),
    "features": ("امکانات پنل تبلیغات تلگرام", "با ابزارهای طراحی کمپین، هدف‌گیری، کیف پول ریالی، گزارش‌های تبلیغاتی و مدیریت درخواست‌های تبلیغات تلگرام آشنا شوید."),
    "how_it_works": ("آموزش شروع تبلیغات تلگرام", "مراحل ساخت کمپین تلگرام ادز، انتخاب مخاطب، تعیین بودجه، بررسی سفارش و پایش نتایج را یاد بگیرید."),
    "pricing": ("هزینه و تعرفه تبلیغات تلگرام", "نحوه محاسبه هزینه تبلیغات تلگرام، CPM، نرخ تبدیل گرام، کارمزد و مبلغ پیش‌فاکتور را بررسی کنید."),
    "faq": ("سوالات متداول تبلیغات تلگرام", "پاسخ سوالات رایج درباره تلگرام ادز، هزینه، هدف‌گیری، انتشار، پرداخت، گزارش‌ها و بازپرداخت."),
    "about": ("درباره تی‌ام‌ادز", "با هدف تی‌ام‌ادز، پلتفرم فارسی مدیریت تبلیغات تلگرام، و اصول شفافیت مالی، حریم خصوصی و گزارش‌گیری آشنا شوید."),
    "contact": ("تماس با ما و پشتیبانی تی‌ام‌ادز", "راهنمای دریافت پشتیبانی تی‌ام‌ادز، ثبت تیکت و پیگیری سوالات درباره تبلیغات تلگرام، سفارش و کیف پول."),
    "terms": ("شرایط استفاده از تی‌ام‌ادز", "شرایط استفاده و مسئولیت‌های مربوط به سفارش و مدیریت تبلیغات تلگرام در تی‌ام‌ادز."),
    "privacy": ("حریم خصوصی تی‌ام‌ادز", "سیاست حریم خصوصی و نحوه پردازش اطلاعات کاربران تی‌ام‌ادز."),
    "refund": ("سیاست بازپرداخت تی‌ام‌ادز", "شرایط درخواست بازپرداخت و بررسی وضعیت مالی سفارش تبلیغات تلگرام."),
    "content_policy": ("قوانین محتوای تبلیغات تلگرام", "ضوابط محتوای تبلیغاتی تی‌ام‌ادز و الزامات بررسی تبلیغ قبل از ارسال."),
}
# Legal documents are still drafts; keep them accessible without promoting indexing.
LEGAL_DRAFTS = {"terms", "privacy", "refund", "content_policy"}
AUTH = {
    "login": ("ورود به تی‌ام‌ادز", "ورود به حساب برای مدیریت کمپین‌ها، کیف پول و گزارش‌های تبلیغات تلگرام."),
    "register": ("ثبت‌نام در تی‌ام‌ادز", "ایجاد حساب کاربری برای طراحی و مدیریت کمپین‌های تبلیغات تلگرام."),
    "password_reset": ("بازیابی رمز عبور", "راهنمای بازیابی دسترسی به حساب تی‌ام‌ادز."),
}


def public_origin():
    raw = str(getattr(settings, "PUBLIC_SITE_URL", "")).strip()
    try:
        parsed = urlsplit(raw)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username
                or parsed.password or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment or parsed.hostname in ("localhost", "127.0.0.1", "::1")):
            return ""
        if any(ch.isspace() for ch in parsed.netloc) or "\\" in parsed.netloc:
            return ""
        _ = parsed.port  # Reject malformed ports.
        return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
    except ValueError:
        return ""


def index_enabled():
    return settings.APP_ENV == "PRODUCTION" and bool(public_origin())


BREADCRUMB_NAMES = {
    "features": "امکانات پنل تبلیغات تلگرام",
    "how_it_works": "آموزش تبلیغات تلگرام",
    "pricing": "هزینه و تعرفه تبلیغات تلگرام",
    "faq": "سوالات متداول تبلیغات تلگرام",
    "about": "درباره ما",
    "contact": "تماس با ما و پشتیبانی",
}


def structured_data(name, canonical):
    """Only public, canonical pages receive factual schema; escape script delimiters."""
    if not canonical:
        return ""
    origin = public_origin()
    site_id = origin + "/#website"
    graph = []
    if name == "home":
        graph.append({"@type": "WebSite", "@id": site_id, "url": canonical,
                      "name": settings.PRODUCT_NAME, "alternateName": "TMADS", "inLanguage": "fa"})
    elif name in BREADCRUMB_NAMES:
        graph.append({"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "صفحه اصلی", "item": origin + reverse("public:home")},
            {"@type": "ListItem", "position": 2, "name": BREADCRUMB_NAMES[name], "item": canonical},
        ]})
    if not graph:
        return ""
    payload = json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False)
    return mark_safe(payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))


def metadata(request):
    match = getattr(request, "resolver_match", None)
    namespace = getattr(match, "namespace", "")
    name = getattr(match, "url_name", "")
    seo = {"robots": "noindex, follow", "canonical": "", "title": "", "description": ""}
    if namespace == "public" and name in PAGES:
        seo["title"], seo["description"] = PAGES[name]
        if settings.APP_ENV == "PRODUCTION" and name not in LEGAL_DRAFTS:
            seo["robots"] = "index, follow"
            if public_origin():
                seo["canonical"] = public_origin() + reverse("public:" + name)
    elif namespace == "accounts" and name in AUTH:
        seo["title"], seo["description"] = AUTH[name]
    if seo["title"]:
        seo["title"] = seo["title"] + " | " + settings.PRODUCT_NAME if name != "about" and name != "contact" and namespace != "accounts" and name not in ("terms", "privacy", "refund") else seo["title"]
    seo["structured_data"] = structured_data(name, seo["canonical"])
    return {"seo": seo}


def robots_txt(request):
    lines = ["User-agent: *", "Allow: /"]
    if index_enabled():
        lines.append("Sitemap: " + public_origin() + reverse("public:sitemap"))
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def sitemap_xml(request):
    if not index_enabled():
        return HttpResponseNotFound("Public sitemap is not configured.", content_type="text/plain")
    root = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for name in PAGES:
        if name in LEGAL_DRAFTS:
            continue
        url = ET.SubElement(root, "url")
        ET.SubElement(url, "loc").text = public_origin() + reverse("public:" + name)
    return HttpResponse(ET.tostring(root, encoding="utf-8", xml_declaration=True), content_type="application/xml")
