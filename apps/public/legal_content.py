from pathlib import Path

from django.conf import settings

LEGAL_DIR = Path(settings.BASE_DIR) / "docs" / "legal"

FALLBACK = {
    "terms": "شرایط استفاده — پیش‌نویس MVP.",
    "privacy": "حریم خصوصی — پیش‌نویس MVP.",
    "refund": "سیاست بازپرداخت — پیش‌نویس MVP.",
    "content": "سیاست محتوای تبلیغاتی — پیش‌نویس MVP.",
}


def load_legal_text(slug: str) -> str:
    path = LEGAL_DIR / f"{slug}.md"
    if path.is_file():
        return path.read_text(encoding="utf-8")
    return FALLBACK.get(slug, "")
