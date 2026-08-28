"""Image storage for uploaded photos (farm, cow, ...).

Uploads to Cloudinary and returns its public HTTPS URL — not local disk.
Local disk was the original approach, but Render's free-tier filesystem is
ephemeral: it gets wiped on every deploy and every restart, which was
silently orphaning every `photo_path` already saved in the database
(confirmed directly — uploaded cow photos started 404ing after the next
deploy, despite the database still pointing at them). Cloudinary's free
tier persists across all of that, since it isn't the app server's own disk.
"""
from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

import cloudinary
import cloudinary.uploader
from PIL import Image, UnidentifiedImageError

from config.settings import settings
from utils.exceptions import AppError
from utils.logger import get_logger

logger = get_logger(__name__)

_MAX_DIMENSION = 1200
_configured = False


class InvalidImageError(AppError):
    """Raised when the selected file is not a readable image."""


def _ensure_configured() -> None:
    """Lazy, once-per-process — mirrors `assistant/generation.py`'s lazy
    Anthropic client so a missing/not-yet-set API key doesn't block the
    app from booting, only the first actual photo upload."""
    global _configured
    if _configured:
        return
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        raise AppError("Photo storage isn't configured yet — ask an admin to set the CLOUDINARY_* environment variables.")
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    _configured = True


def save_image(source_path: Path, *, subdir: str, prefix: str) -> str:
    """Downscale, then upload to Cloudinary under `<subdir>/<prefix>_<id>`.
    Returns the photo's public HTTPS URL (stored as-is in `photo_path` —
    the mobile client uses it directly, no `/media` prefix needed)."""
    _ensure_configured()

    downscaled_path = source_path.with_name(f"{source_path.stem}_upload.jpg")
    try:
        with Image.open(source_path) as image:
            # Normalize everything to JPEG — photos of farms/cows don't need
            # per-format fidelity, and a single format keeps storage simple.
            image = image.convert("RGB")
            image.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION))
            image.save(downscaled_path, format="JPEG", quality=88)
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError(f"Could not read image file: {source_path.name}") from exc

    public_id = f"{prefix}_{uuid.uuid4().hex[:8]}"
    try:
        result = cloudinary.uploader.upload(str(downscaled_path), folder=subdir, public_id=public_id)
    finally:
        downscaled_path.unlink(missing_ok=True)

    url = result["secure_url"]
    logger.info("Uploaded image to Cloudinary: %s", url)
    return url


def delete_image(url: Optional[str]) -> None:
    """No-op for anything that isn't a Cloudinary URL — covers both `None`
    and the now-unrecoverable local-relative-path values left over from
    before this module switched storage backends (the files behind those
    are already gone; there's nothing left to delete)."""
    if not url or not url.startswith("http"):
        return
    _ensure_configured()
    match = re.search(r"/upload/(?:v\d+/)?(?P<public_id>.+?)(?:\.\w+)?$", url)
    if not match:
        return
    cloudinary.uploader.destroy(match.group("public_id"))
