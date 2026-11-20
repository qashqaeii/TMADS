from django.shortcuts import render
from django.contrib.staticfiles import finders
from django.templatetags.static import static

from apps.core.templatetags.features_assets import feature_asset


def home(request):
    return render(request, "public/home.html")


def features(request):
    return render(request, "public/features.html")


def how_it_works(request):
    return render(request, "public/how_it_works.html")


def pricing(request):
    return render(request, "public/pricing.html")


FAQ_ART_FALLBACKS = {
    "hero": "features-hero",
    "support": "feature-support",
    "wallet": "feature-wallet",
    "targeting": "feature-targeting",
    "search": "feature-targeting",
    "review": "feature-security",
    "analytics": "feature-analytics",
}


def faq(request):
    artwork = {}
    for role, fallback in FAQ_ART_FALLBACKS.items():
        path = f"img/faq/tmads_faq_{role}.webp"
        artwork[role] = static(path) if finders.find(path) else feature_asset(fallback)
    return render(request, "public/faq.html", {"faq_art": artwork})


CONTACT_ART = {
    "hero": ("img/faq/tmads_faq_support.webp", "feature-support"),
    "campaign": ("img/workflow/tmads_workflow_campaign.webp", "feature-campaign"),
    "wallet": ("img/pricing/tmads_pricing_wallet_and_coins.webp", "feature-wallet"),
    "questions": ("img/faq/tmads_faq_search.webp", "feature-targeting"),
    "security": ("img/faq/tmads_faq_review.webp", "feature-security"),
}


def contact(request):
    artwork = {
        role: static(path) if finders.find(path) else feature_asset(fallback)
        for role, (path, fallback) in CONTACT_ART.items()
    }
    return render(request, "public/contact.html", {"contact_art": artwork})


ABOUT_ART = {
    "hero": ("img/workflow/tmads_workflow_hero.webp", "features-hero"),
    "wallet": ("img/pricing/tmads_pricing_wallet_and_coins.webp", "feature-wallet"),
    "analytics": ("img/faq/tmads_faq_analytics.webp", "feature-analytics"),
    "trust": ("img/faq/tmads_faq_review.webp", "feature-security"),
    "mission": ("img/pricing/tmads_pricing_roi_target.webp", "feature-targeting"),
    "launch": ("img/workflow/tmads_workflow_publish.webp", "feature-channels"),
}


def about(request):
    artwork = {
        role: static(path) if finders.find(path) else feature_asset(fallback)
        for role, (path, fallback) in ABOUT_ART.items()
    }
    return render(request, "public/about.html", {"about_art": artwork})


from .legal_content import load_legal_text, structure_legal_text


def _legal(request, slug: str, title: str):
    text = load_legal_text(slug)
    artwork = {
        "terms": "img/pricing/tmads_pricing_invoice_checklist.webp",
        "privacy": "img/faq/tmads_faq_review.webp",
        "refund": "img/pricing/tmads_pricing_refund_cycle.webp",
        "content": "img/workflow/tmads_workflow_review.webp",
    }
    fallback = {
        "terms": "feature-security", "privacy": "feature-security",
        "refund": "feature-wallet", "content": "feature-campaign",
    }
    path = artwork[slug]
    support = "img/faq/tmads_faq_support.webp"
    return render(
        request,
        "public/legal_page.html",
        {
            "title": title, "slug": slug, "body_text": text,
            "legal_document": structure_legal_text(text),
            "legal_art": static(path) if finders.find(path) else feature_asset(fallback[slug]),
            "legal_support_art": static(support) if finders.find(support) else feature_asset("feature-support"),
        },
    )


def terms(request):
    return _legal(request, "terms", "شرایط استفاده")


def privacy(request):
    return _legal(request, "privacy", "حریم خصوصی")


def refund(request):
    return _legal(request, "refund", "سیاست بازپرداخت")


def content_policy(request):
    return _legal(request, "content", "سیاست محتوای تبلیغاتی")
