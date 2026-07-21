"""QR code generation for cow identification tags."""
from __future__ import annotations

import uuid

import qrcode

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


def generate_qr_value() -> str:
    """A short, unique, scan-friendly identifier — not a database ID, since
    that would leak internal row numbers onto a physical tag."""
    return f"DTA-{uuid.uuid4().hex[:10].upper()}"


def generate_qr_image(value: str, *, subdir: str, prefix: str) -> str:
    """Render `value` as a QR code PNG under assets/images/<subdir>/, return a path relative to ASSETS_DIR."""
    target_dir = settings.ASSETS_DIR / "images" / subdir
    target_dir.mkdir(parents=True, exist_ok=True)

    image = qrcode.make(value)
    filename = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
    target_path = target_dir / filename
    image.save(target_path)

    relative_path = target_path.relative_to(settings.ASSETS_DIR).as_posix()
    logger.info("Generated QR code %s", relative_path)
    return relative_path
