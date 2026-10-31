"""The table top: a 1v1 take on the MTG EDH table's look, drawn procedurally.

The save uses TTS's custom rectangle table (``Table_Custom``). Measured in TTS
(2026-10-29): its felt is at y = 0.96 like ``Table_RPG``, the flat top runs to
about x ±55, z ±37, and the image covers an inset of ``TABLE_W`` x ``TABLE_H``
units, centred, top edge toward +z (Red's side), not mirrored.

Each player gets one wide painted mat (``PANEL_W`` x 16, centred ``MAT_MID`` from
the middle line: the in-game playmat, 44 wide, lies over its middle) inside a
light wood frame with a plain gold trim (no title or logo), and the zone board's art (``zones.render_board``) painted where the board
lies during a game, so the Library / Graveyard / Exile slots show before the
board appears and line up with it after. White's half is drawn as-is (White sits
at -z, the image's bottom); Red's is the same panel turned 180 degrees.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from draft_duel import zones
from draft_duel.sheets import save_hashed

TABLE_W, TABLE_H = 88.4, 52.2      # table units covered by the image
SIZE = (4096, 2419)                # same shape as the area (TTS stretches the image to it)
PPU = SIZE[0] / TABLE_W            # pixels per table unit

PANEL_W = 62.0                             # painted mat width (the EDH mats fill most of the table)
MAT_D, MAT_MID = 16.0, 9.5                 # depth and centre from the middle line, as the in-game playmat
FRAME = 0.35                               # light wood around each mat

RGB = tuple[int, int, int]
MAT_COLORS: dict[str, tuple[RGB, RGB]] = {   # centre, edge
    "White": ((70, 58, 52), (20, 17, 16)),
    "Red": ((44, 50, 70), (13, 15, 22)),
}
GOLD = (176, 138, 70)


def _px(units: float) -> int:
    return round(units * PPU)


def _wood(size: tuple[int, int], rng: random.Random, dark: int, light: int) -> Image.Image:
    """Grey wood grain: thin streaks (noise stretched far along x) over a faint broad wash."""
    w, h = size
    out = None
    for cols, rows, weight in ((6, max(8, h // 60), 1.0), (10, max(16, h // 3), 0.7), (40, max(16, h // 2), 0.25)):
        noise = Image.new("L", (cols, rows))
        noise.putdata([rng.randint(0, 255) for _ in range(cols * rows)])
        layer = noise.resize((w, h), Image.BICUBIC)
        out = layer if out is None else Image.blend(out, layer, weight)
    grain = out.filter(ImageFilter.GaussianBlur(0.8)).point(lambda v: dark + (light - dark) * v // 255)
    return grain.convert("RGB")


def _radial(size: tuple[int, int], center: RGB, edge: RGB) -> Image.Image:
    mask = Image.radial_gradient("L").resize(size)
    return Image.composite(Image.new("RGB", size, edge), Image.new("RGB", size, center), mask)


def render_panel(color: str) -> Image.Image:
    """One player's mat with its frame, gold trim and zone strip; the owner's edge at the bottom."""
    rng = random.Random(f"panel-{color}")
    pw, ph = _px(PANEL_W + 2 * FRAME), _px(MAT_D + 2 * FRAME)
    panel = _wood((pw, ph), rng, 118, 170)
    d = ImageDraw.Draw(panel)
    f = _px(FRAME)
    d.rectangle((0, 0, pw - 1, ph - 1), outline=(60, 60, 60), width=3)
    mat = _radial((pw - 2 * f, ph - 2 * f), *MAT_COLORS[color])
    panel.paste(mat, (f, f))
    d.rectangle((f - 2, f - 2, pw - f + 1, ph - f + 1), outline=(40, 40, 40), width=3)

    inset = f + _px(0.7)
    d.rounded_rectangle((inset, inset, pw - inset, ph - inset), radius=_px(1.2), outline=GOLD, width=5)

    # The zone board's art where the board lies in a game (owner-relative u, d from the middle).
    b = zones.BOARD
    board = zones.render_board().resize((_px(b["w"]), _px(b["h"])), Image.LANCZOS)
    left = _px(b["u"] - b["w"] / 2 + PANEL_W / 2 + FRAME)
    top = _px(b["d"] - b["h"] / 2 - (MAT_MID - MAT_D / 2) + FRAME)
    panel.paste(board, (left, top))
    return panel


def render_table() -> Image.Image:
    """The whole table image (the same pixels every time)."""
    rng = random.Random("table")
    img = _wood(SIZE, rng, 62, 110)
    # Soft darker blotches, like the EDH table's faint swirls.
    blot = Image.new("L", SIZE, 0)
    bd = ImageDraw.Draw(blot)
    for _ in range(40):
        x, y, r = rng.uniform(0, SIZE[0]), rng.uniform(0, SIZE[1]), rng.uniform(80, 260)
        bd.ellipse((x - r, y - r, x + r, y + r), fill=rng.randint(8, 18))
    img = ImageChops.subtract(img, Image.merge("RGB", [blot.filter(ImageFilter.GaussianBlur(60))] * 3))

    d = ImageDraw.Draw(img)
    edge = _px(1.0)
    d.rectangle((0, 0, SIZE[0] - 1, SIZE[1] - 1), outline=(18, 18, 18), width=edge)
    d.rectangle((edge, edge, SIZE[0] - edge, SIZE[1] - edge), outline=(150, 150, 150), width=3)

    cx, cy = SIZE[0] / 2, SIZE[1] / 2
    for color, flip in (("White", False), ("Red", True)):
        panel = render_panel(color)
        if flip:
            panel = panel.rotate(180)
        x = round(cx - panel.width / 2)
        near = MAT_MID - MAT_D / 2 - FRAME   # the panel's edge nearest the middle line
        y = round(cy + _px(near)) if not flip else round(cy - _px(near) - panel.height)
        img.paste(panel, (x, y))
    return img


def render_all(out_dir: Path) -> str:
    """Writes the table image as a hashed JPEG and returns its file name."""
    return save_hashed(render_table(), out_dir, "table")
