from django.shortcuts import render


def home(request):
    return render(request, "public/home.html")


def features(request):
    return render(request, "public/features.html")


def how_it_works(request):
    return render(request, "public/how_it_works.html")


def pricing(request):
    return render(request, "public/pricing.html")


def faq(request):
    return render(request, "public/faq.html")


def contact(request):
    return render(request, "public/contact.html")


def about(request):
    return render(request, "public/about.html")


from .legal_content import load_legal_text


def _legal(request, slug: str, title: str):
    return render(
        request,
        "public/legal_page.html",
        {"title": title, "slug": slug, "body_text": load_legal_text(slug)},
    )


def terms(request):
    return _legal(request, "terms", "شرایط استفاده")


def privacy(request):
    return _legal(request, "privacy", "حریم خصوصی")


def refund(request):
    return _legal(request, "refund", "سیاست بازپرداخت")


def content_policy(request):
    return _legal(request, "content", "سیاست محتوای تبلیغاتی")
