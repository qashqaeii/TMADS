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


def structure_legal_text(text: str) -> dict:
    """Render the legal documents' heading/paragraph/list subset as escaped data."""
    import re

    document = {"heading": "", "intro": [], "sections": []}
    target = document["intro"]
    paragraph = []
    items = []

    def flush():
        if paragraph:
            target.append({"kind": "paragraph", "text": "\n".join(paragraph)})
            paragraph.clear()
        if items:
            target.append({"kind": "list", "items": items.copy()})
            items.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        heading = re.fullmatch(r"(#{1,6})[ \t]+(.+)", line)
        if heading:
            flush()
            label = heading.group(2)
            if len(heading.group(1)) == 1 and not document["heading"] and not document["intro"] and not document["sections"]:
                document["heading"] = label
            else:
                section = {"title": label, "id": f"legal-clause-{len(document['sections']) + 1}", "blocks": []}
                document["sections"].append(section)
                target = section["blocks"]
            continue
        if line.startswith(("- ", "* ")):
            if paragraph:
                flush()
            items.append(line[2:])
        else:
            if items:
                flush()
            paragraph.append(line)
    flush()
    return document
