from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for path in ROOT.glob("templates/**/*.html"):
    text = path.read_text(encoding="utf-8")
    if "motion" not in text and "Entry" not in text and "Input" not in text:
        continue
    text = text.replace("motion", "div")
    text = text.replace("<Entry ", "<div ")
    text = text.replace("<Input ", "<div ")
    path.write_text(text, encoding="utf-8")
    print("fixed", path.relative_to(ROOT))
