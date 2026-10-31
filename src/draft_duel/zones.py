"""The zone board: each player's Library / Graveyard / Exile slots, Draw / Untap buttons and
Scry / Surveil / Mulligan beside them.

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
# Real TTS buttons sit on these strips, between the graveyard and the library. Buttons with a ``u``
# float just right of the board (they belong to it, but the image paints no strip for them): Scry
# beside Untap, Surveil beside Draw, Mulligan above Scry (away from the sideboard pile).
SIDE_U = BOARD["u"] + BOARD["w"] / 2 + 0.2 + 1.1
BUTTONS = {
    "untap": {"d": 11.45, "w": 2.6, "h": 0.9, "label": "Untap"},
    "draw": {"d": 12.55, "w": 2.6, "h": 0.9, "label": "Draw"},
    "mulligan": {"u": SIDE_U, "d": 10.35, "w": 2.2, "h": 0.9, "label": "Mulligan"},
    "scry": {"u": SIDE_U, "d": 11.45, "w": 2.2, "h": 0.9, "label": "Scry"},
    "surveil": {"u": SIDE_U, "d": 12.55, "w": 2.2, "h": 0.9, "label": "Surveil"},
}
# Cards being scried or surveilled float face-up (hidden from the opponent) in a row from here
# toward the owner's left, one card further each click.
LOOK = {"u": BOARD["u"] - BOARD["w"] / 2 - 0.3 - 1.1, "d": 9.6, "step": 2.5}
# Off the board: the sideboard pile (beyond the mat's right edge) and the dice (owner's left corner).
SIDEBOARD = {"u": 25.5, "d": 14.95}
DICE = [
    {"type": "Die_20", "u": -24.2, "d": 14.8},
    {"type": "Die_6", "u": -25.3, "d": 12.6},
    {"type": "Die_6", "u": -23.1, "d": 12.6},
]

LAYOUT: dict[str, Any] = {"board": BOARD, "slots": SLOTS, "buttons": BUTTONS,
                          "sideboard": SIDEBOARD, "dice": DICE, "look": LOOK}

MAT_W = 44.0       # the playmat LAYOUT is drawn for
BELOW_MAT_D = 19.6  # between a mat's hand-side edge (d 17.5) and a four-player hand zone (d 21.5+)


def layout_for(mat_w: float) -> dict[str, Any]:
    """The layout for a playmat ``mat_w`` wide: ``LAYOUT`` with the board at that mat's right edge.

    A narrower mat (the four-player table's 38) leaves no room beside it, so the
    sideboard pile and the dice go just past its hand-side edge instead: the
    pile under the board, the dice in the owner's left corner.
    """
    if mat_w == MAT_W:
        return LAYOUT
    shift = (mat_w - MAT_W) / 2
    board = {**BOARD, "u": BOARD["u"] + shift}
    left = -mat_w / 2
    return {
        "board": board,
        "slots": SLOTS,
        "buttons": {k: ({**b, "u": b["u"] + shift} if "u" in b else b) for k, b in BUTTONS.items()},
        "sideboard": {"u": board["u"], "d": BELOW_MAT_D},
        "dice": [{"type": "Die_20", "u": left + 1.5, "d": BELOW_MAT_D},
                 {"type": "Die_6", "u": left + 3.2, "d": BELOW_MAT_D},
                 {"type": "Die_6", "u": left + 4.6, "d": BELOW_MAT_D}],
        "look": {**LOOK, "u": LOOK["u"] + shift},
    }

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
    for button in (b for b in BUTTONS.values() if "u" not in b):
        draw.rounded_rectangle(_box(BOARD["u"], button["d"], button["w"], button["h"]), radius=14, fill=BUTTON_WELL)
    return img


def render_all(out_dir: Path) -> str:
    """Writes the board as a hashed JPEG and returns its file name."""
    return save_hashed(render_board(), out_dir, "zones")
