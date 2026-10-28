"""Render card images into Tabletop Simulator deck sheets (10 x 7 grids)."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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


def render_card_back() -> Image.Image:
    """A plain original card back (avoids reusing the trademarked Magic back)."""
    img = Image.new("RGB", (CARD_W * 2, CARD_H * 2), "#1b1f3a")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    for inset, color in ((18, "#c9a227"), (34, "#3b4378"), (40, "#c9a227")):
        draw.rounded_rectangle((inset, inset, w - inset, h - inset), radius=40, outline=color, width=6)
    try:
        font = ImageFont.truetype("arialbd.ttf", 96)
        small = ImageFont.truetype("arial.ttf", 52)
    except OSError:
        font = small = ImageFont.load_default()
    draw.text((w / 2, h / 2 - 60), "LSV CUBE", font=font, fill="#c9a227", anchor="mm")
    draw.text((w / 2, h / 2 + 60), "Duel Draft", font=small, fill="#e8e8f0", anchor="mm")
    return img


def save_hashed(img: Image.Image, out_dir: Path, prefix: str) -> str:
    """Save as JPEG named by content hash, so Tabletop Simulator never shows a stale cached sheet."""
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
    data = buf.getvalue()
    name = f"{prefix}-{hashlib.sha1(data).hexdigest()[:12]}.jpg"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / name).write_bytes(data)
    return name
