"""Generate web-sized RGBA derivatives of the checked-in feature artwork.

Original masters are kept untouched. No network access is required.
"""
from pathlib import Path
from tempfile import NamedTemporaryFile

from PIL import Image, ImageOps

ASSET_DIR = Path(__file__).resolve().parents[1] / "static" / "img" / "features"
TRANSPARENT_ART = {
    "features-hero": "telegram_glassmorphism_analytics_hero",
    "feature-campaign": "glowing_campaign_studio_megaphone",
    "feature-targeting": "neon_glass_audience_targeting_icon",
    "feature-channels": "neon_glass_telegram_broadcast_icon",
    "feature-bots": "neon_glass_robot_mini_app_icon",
    "feature-analytics": "neon_glass_analytics_orb",
    "feature-wallet": "neon_glass_wallet_and_coins",
    "feature-security": "glowing_blue_glass_shield_checkmark",
    "feature-control": "neon_glass_control_sliders",
    "feature-performance": "neon_glass_telegram_broadcast_icon",
    "feature-support": "neon_glass_support_headset"
}
SPECS = {name: 1200 if role == "features-hero" else 480
         for role, name in TRANSPARENT_ART.items()}


def optimize(directory=ASSET_DIR):
    directory = Path(directory)
    for name, max_size in SPECS.items():
        source = directory / f"{name}.webp"
        target = directory / f"{name}.optimized.webp"
        if not source.is_file():
            continue
        if target.is_file() and target.stat().st_mtime_ns >= source.stat().st_mtime_ns:
            continue
        with Image.open(source) as original:
            image = ImageOps.exif_transpose(original).convert("RGBA")
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            with NamedTemporaryFile(dir=directory, suffix=".webp.tmp", delete=False) as temporary:
                temp = Path(temporary.name)
            try:
                image.save(temp, "WEBP", quality=85, alpha_quality=100, method=4)
                temp.replace(target)
            finally:
                temp.unlink(missing_ok=True)


if __name__ == "__main__":
    optimize()
