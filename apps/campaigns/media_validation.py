"""Bounded local media validation; uploaded files remain private drafts."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import warnings
from pathlib import Path

from django.core.files.uploadedfile import UploadedFile
from PIL import Image

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_VIDEO_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 24_000_000
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4"}
IMAGE_FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}


def validate_ad_image(upload: UploadedFile) -> list[str]:
    if not 0 < upload.size <= MAX_IMAGE_BYTES:
        return ["حجم تصویر باید حداکثر ۵ مگابایت باشد."]
    suffix = Path(upload.name or "").suffix.lower()
    if suffix not in ALLOWED_IMAGE_EXT:
        return ["فرمت تصویر مجاز نیست (JPG, PNG, WebP)."]
    try:
        upload.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as img:
                if img.format != IMAGE_FORMATS[suffix] or img.width * img.height > MAX_IMAGE_PIXELS:
                    return ["نوع یا ابعاد واقعی تصویر معتبر نیست."]
                if getattr(img, "is_animated", False):
                    return ["تصویر متحرک مجاز نیست."]
                img.verify()
            upload.seek(0)
            with Image.open(upload) as img:
                img.load()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        return ["فایل تصویر سالم و معتبر نیست."]
    finally:
        upload.seek(0)
    return []


def validate_ad_video(upload: UploadedFile) -> list[str]:
    if not 0 < upload.size <= MAX_VIDEO_BYTES:
        return ["حجم ویدیو باید حداکثر ۲۰ مگابایت باشد."]
    if Path(upload.name or "").suffix.lower() != ".mp4":
        return ["فقط MP4 پشتیبانی می‌شود."]
    probe = shutil.which("ffprobe")
    if not probe:
        return ["بررسی امن ویدیو در این محیط در دسترس نیست؛ فعلاً از تصویر استفاده کنید."]
    try:
        upload.seek(0)
        # ffprobe receives only a local file, with all network protocols disabled.
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "upload.mp4"
            with path.open("wb") as out:
                for chunk in upload.chunks():
                    out.write(chunk)
            with path.open("rb") as source:
                head = source.read(12)
            if len(head) < 12 or head[4:8] != b"ftyp":
                return ["ساختار فایل MP4 معتبر نیست."]
            result = subprocess.run(
                [probe, "-v", "error", "-protocol_whitelist", "file", "-probesize", "5000000",
                 "-analyzeduration", "5000000", "-show_entries",
                 "format=format_name,duration:stream=codec_type,codec_name,width,height",
                 "-of", "json", str(path)],
                capture_output=True, timeout=8, check=True,
            )
            info = json.loads(result.stdout)
        fmt = info.get("format") or {}
        streams = info.get("streams") or []
        videos = [x for x in streams if x.get("codec_type") == "video"]
        duration = float(fmt.get("duration") or 0)
        if ("mp4" not in str(fmt.get("format_name", "")).split(",")
                or not 0 < duration <= 3600 or len(videos) != 1
                or videos[0].get("codec_name") != "h264"
                or not 0 < int(videos[0].get("width", 0)) * int(videos[0].get("height", 0)) <= MAX_IMAGE_PIXELS
                or any(x.get("codec_type") not in {"video", "audio"} for x in streams)):
            return ["ویدیو باید MP4 سالم با کدک H.264 و ابعاد معتبر باشد."]
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError):
        return ["فایل ویدیو سالم یا قابل بررسی نیست."]
    finally:
        upload.seek(0)
    return []


def validate_creative_media(upload):
    if not upload:
        return []
    suffix = Path(upload.name or "").suffix.lower()
    if suffix in ALLOWED_VIDEO_EXT:
        return validate_ad_video(upload)
    return validate_ad_image(upload)
