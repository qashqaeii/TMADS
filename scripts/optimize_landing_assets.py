"""Build lightweight landing artwork from the checked-in PNG masters.

Run directly, or automatically via manage.py runserver / collectstatic.
The outputs are deterministic, local-only and safe to regenerate.
"""
from pathlib import Path

from PIL import Image, ImageOps

ASSET_DIR = Path(__file__).resolve().parents[1] / "static" / "img" / "landing"
SPECS = {
    "hero-background": (1600, 80),
    "hero-dashboard": (1200, 84),
    "telegram-banner": (1100, 82),
    "orbit-dark": (1440, 80),
    "channels": (360, 82),
    "users-targeting": (360, 82),
    "bots-miniapps": (360, 82),
    "search": (360, 82),
    "order-review": (360, 82),
    "analytics-budget": (360, 82),
}


def optimize(directory=ASSET_DIR):
    directory = Path(directory)
    for name, (max_width, quality) in SPECS.items():
        source = directory / f"{name}.png"
        target = directory / f"{name}.webp"
        if not source.is_file():
            raise FileNotFoundError(source)
        if target.is_file() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
            continue
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
            temp = target.with_suffix(".webp.tmp")
            image.save(temp, "WEBP", quality=quality, method=6)
            temp.replace(target)


if __name__ == "__main__":
    optimize()
