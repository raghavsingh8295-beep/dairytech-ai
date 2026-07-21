"""Image storage for uploaded photos (farm, cow, ...).

Copies a user-selected image into assets/images/<subdir>/, generating a
collision-safe filename and downscaling large images so the app doesn't
accumulate multi-megabyte originals. Returns a path relative to
ASSETS_DIR so stored paths stay portable across machines.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

from config.settings import settings
from utils.exceptions import AppError
from utils.logger import get_logger

logger = get_logger(__name__)

_MAX_DIMENSION = 1200


class InvalidImageError(AppError):
    """Raised when the selected file is not a readable image."""


def save_image(source_path: Path, *, subdir: str, prefix: str) -> str:
    """Copy+downscale an image into assets/images/<subdir>/, return a path relative to ASSETS_DIR."""
    target_dir = settings.ASSETS_DIR / "images" / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(source_path) as image:
            # Normalize everything to JPEG — photos of farms/cows don't need
            # per-format fidelity, and a single format keeps storage simple.
            image = image.convert("RGB")
            image.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION))
            filename = f"{prefix}_{uuid.uuid4().hex[:8]}.jpg"
            target_path = target_dir / filename
            image.save(target_path, format="JPEG", quality=88)
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError(f"Could not read image file: {source_path.name}") from exc

    relative_path = target_path.relative_to(settings.ASSETS_DIR).as_posix()
    logger.info("Saved image %s", relative_path)
    return relative_path


def delete_image(relative_path: Optional[str]) -> None:
    if not relative_path:
        return
    full_path = settings.ASSETS_DIR / relative_path
    if full_path.exists():
        full_path.unlink()
