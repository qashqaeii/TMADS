"""Local ad media validation before optional remote upload."""

from __future__ import annotations

import imghdr
from io import BytesIO

from django.core.files.uploadedfile import UploadedFile

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_VIDEO_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4"}


def validate_ad_image(upload: UploadedFile) -> list[str]:
    errors: list[str] = []
    if upload.size > MAX_IMAGE_BYTES:
        errors.append("حجم تصویر بیش از ۵ مگابایت است.")
    name = (upload.name or "").lower()
    if not any(name.endswith(ext) for ext in ALLOWED_IMAGE_EXT):
        errors.append("فرمت تصویر مجاز نیست (JPG, PNG, WebP).")
    head = upload.read(512)
    upload.seek(0)
    kind = imghdr.what(None, head)
    if kind not in ("jpeg", "png", "webp"):
        try:
            from PIL import Image

            with Image.open(BytesIO(head)) as img:
                img.verify()
        except Exception:
            errors.append("فایل تصویر معتبر نیست.")
    return errors


def validate_ad_video(upload: UploadedFile) -> list[str]:
    errors: list[str] = []
    if upload.size > MAX_VIDEO_BYTES:
        errors.append("حجم ویدیو بیش از ۲۰ مگابایت است.")
    name = (upload.name or "").lower()
    if not any(name.endswith(ext) for ext in ALLOWED_VIDEO_EXT):
        errors.append("فقط MP4 پشتیبانی می‌شود.")
    return errors
