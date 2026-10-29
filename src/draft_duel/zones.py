"""The zone board: each player's Library / Graveyard / Exile slots and Draw / Untap buttons.

One board per seat lies on the owner's right edge of their battlefield while a
game is on (borrowed from the popular MTG EDH table). This module is the single
source of truth for its geometry: the image is drawn from ``LAYOUT`` and the
same numbers reach the in-game script as ``ZONES_JSON``, where the library is
gathered into its slot and the Draw / Untap buttons are placed.

Positions are owner-relative, in table units: ``u`` across the table (positive
= the owner's right), ``d`` away from the middle line toward the owner's hand.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from draft_duel.sheets import save_hashed

PX_PER_UNIT = 160

# The board: 3 x 13.3 units, inside the 44 x 16 playmat's right edge (u <= 22).
BOARD = {"u": 20.2, "d": 10.15, "w": 3.0, "h": 13.3}
# Card slots (a card is 2.2 x 3.06): exile nearest the middle, library nearest the hand.
SLOTS = {
    "exile": {"d": 5.35, "w": 2.5, "h": 3.3, "label": "EXILE"},
    "graveyard": {"d": 9.05, "w": 2.5, "h": 3.3, "label": "GRAVEYARD"},
    "library": {"d": 14.95, "w": 2.5, "h": 3.3, "label": "LIBRARY"},
}
# Real TTS buttons sit on these strips, between the graveyard and the library.
BUTTONS = {
    "untap": {"d": 11.45, "w": 2.6, "h": 0.9, "label": "Untap"},
    "draw": {"d": 12.55, "w": 2.6, "h": 0.9, "label": "Draw"},
}
# Off the board: the sideboard pile (beyond the mat's right edge) and the dice (owner's left corner).
SIDEBOARD = {"u": 25.5, "d": 14.95}
DICE = [
    {"type": "Die_20", "u": -24.2, "d": 14.8},
    {"type": "Die_6", "u": -25.3, "d": 12.6},
    {"type": "Die_6", "u": -23.1, "d": 12.6},
]

LAYOUT: dict[str, Any] = {"board": BOARD, "slots": SLOTS, "buttons": BUTTONS,
                          "sideboard": SIDEBOARD, "dice": DICE}

BOARD_SIZE = (round(BOARD["w"] * PX_PER_UNIT), round(BOARD["h"] * PX_PER_UNIT))

BACKGROUND = (24, 28, 34)
FRAME = (150, 128, 82)
SLOT_LINE = (190, 196, 204)
SLOT_FILL = (34, 39, 47)
LABEL = (150, 158, 168)
BUTTON_WELL = (16, 18, 22)


def _box(cx_u: float, d: float, w: float, h: float) -> tuple[float, float, float, float]:
    """Pixel box of a ``w`` x ``h`` area centred at (``cx_u``, ``d``); the image top faces the middle line."""
    left_u = BOARD["u"] - BOARD["w"] / 2
    top_d = BOARD["d"] - BOARD["h"] / 2
    x0 = (cx_u - w / 2 - left_u) * PX_PER_UNIT
    y0 = (d - h / 2 - top_d) * PX_PER_UNIT
    return x0, y0, x0 + w * PX_PER_UNIT, y0 + h * PX_PER_UNIT


def render_board() -> Image.Image:
    """Draws the zone board (the same pixels every time)."""
    img = Image.new("RGB", BOARD_SIZE, BACKGROUND)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((4, 4, BOARD_SIZE[0] - 5, BOARD_SIZE[1] - 5), radius=24, outline=FRAME, width=6)
    font = ImageFont.load_default(size=58)
    for slot in SLOTS.values():
        box = _box(BOARD["u"], slot["d"], slot["w"], slot["h"])
        draw.rounded_rectangle(box, radius=20, fill=SLOT_FILL, outline=SLOT_LINE, width=5)
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        draw.text((cx, cy), slot["label"], fill=LABEL, font=font, anchor="mm")
    for button in BUTTONS.values():
        draw.rounded_rectangle(_box(BOARD["u"], button["d"], button["w"], button["h"]), radius=14, fill=BUTTON_WELL)
    return img


def render_all(out_dir: Path) -> str:
    """Writes the board as a hashed JPEG and returns its file name."""
    return save_hashed(render_board(), out_dir, "zones")
