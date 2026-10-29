"""Render card images into Tabletop Simulator deck sheets (10 x 7 grids)."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image

CARD_W, CARD_H = 409, 570  # 10 x 7 grid stays under 4096px, which every GPU can load
COLS, ROWS = 10, 7
PER_SHEET = COLS * ROWS - 1  # TTS reserves the last slot for the hidden-card image
JPEG_QUALITY = 87


def chunk(items: list, size: int = PER_SHEET) -> list[list]:
    """Split ``items`` into sheet-sized groups."""
    return [items[i : i + size] for i in range(0, len(items), size)]


def render_sheet(images: list[Path]) -> Image.Image:
    """Paste up to ``PER_SHEET`` card images into one sheet, left to right, top to bottom."""
    if len(images) > PER_SHEET:
        raise ValueError(f"{len(images)} images do not fit on one sheet ({PER_SHEET} max)")
    sheet = Image.new("RGB", (CARD_W * COLS, CARD_H * ROWS), "black")
    for i, path in enumerate(images):
        with Image.open(path) as img:
            card = img.convert("RGB").resize((CARD_W, CARD_H), Image.LANCZOS)
        sheet.paste(card, ((i % COLS) * CARD_W, (i // COLS) * CARD_H))
    return sheet


def card_back(path: Path) -> Image.Image:
    """The official Magic card back (downloaded from Scryfall), as an RGB image."""
    with Image.open(path) as img:
        return img.convert("RGB")


def save_hashed(img: Image.Image, out_dir: Path, prefix: str) -> str:
    """Save as JPEG named by content hash, so Tabletop Simulator never shows a stale cached sheet."""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    data = buf.getvalue()
    name = f"{prefix}-{hashlib.sha1(data).hexdigest()[:12]}.jpg"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_bytes(data)
    return name
