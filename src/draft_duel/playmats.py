"""Playmat artwork, drawn procedurally so it is ours to host (no copyrighted mats).

Each theme is a function that paints a ``MAT_SIZE`` image. Drawing is seeded,
so the same code always produces the same pixels (and the same hashed file
name), and a rebuild only pushes mats that actually changed.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageStat

from draft_duel import zones
from draft_duel.sheets import save_hashed

# Matches the in-game mat (44 x 16 table units over each player's battlefield).
MAT_SIZE = (2048, 744)
W, H = MAT_SIZE

RGB = tuple[int, int, int]


# ------------------------------------------------------------------ helpers


def _vgradient(top: RGB, bottom: RGB, size: tuple[int, int] = MAT_SIZE) -> Image.Image:
    """Vertical blend from ``top`` to ``bottom``."""
    mask = Image.linear_gradient("L").resize(size)
    return Image.composite(Image.new("RGB", size, bottom), Image.new("RGB", size, top), mask)


def _radial(center: RGB, edge: RGB, size: tuple[int, int] = MAT_SIZE) -> Image.Image:
    """Blend from ``center`` out to ``edge``."""
    mask = Image.radial_gradient("L").resize(size)
    return Image.composite(Image.new("RGB", size, edge), Image.new("RGB", size, center), mask)


def _layer() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", MAT_SIZE, "black")
    return img, ImageDraw.Draw(img)


def _glow(base: Image.Image, layer: Image.Image, blur: float, keep_sharp: bool = True) -> Image.Image:
    """Adds a light layer on top of ``base`` with a soft glow around it."""
    out = ImageChops.screen(base, layer.filter(ImageFilter.GaussianBlur(blur)))
    return ImageChops.screen(out, layer) if keep_sharp else out


def _stars(base: Image.Image, rng: random.Random, n: int, bright: int = 20) -> Image.Image:
    layer, d = _layer()
    for _ in range(n):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0.6, 1.8)
        v = rng.randint(150, 255)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(v, v, min(255, v + 20)))
    for _ in range(bright):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(2.5, 4)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 240))
    return _glow(base, layer, 3)


def _finish(img: Image.Image, brightness: float = 0.88) -> Image.Image:
    """Darkens the edges a little and the whole mat slightly, so cards stand out."""
    vignette = Image.radial_gradient("L").resize(MAT_SIZE).point(lambda v: 255 - int(v * 0.45))
    img = ImageChops.multiply(img, Image.merge("RGB", (vignette, vignette, vignette)))
    return ImageEnhance.Brightness(img).enhance(brightness)


def _sine_points(y0: float, amp: float, wavelength: float, phase: float, step: int = 8) -> list[tuple[float, float]]:
    return [(x, y0 + amp * math.sin(2 * math.pi * x / wavelength + phase)) for x in range(-step, W + step, step)]


# ------------------------------------------------------------------ themes


def starry_night(rng: random.Random) -> Image.Image:
    """Deep blue night with a glowing crescent moon."""
    img = _stars(_vgradient((10, 14, 48), (44, 24, 78)), rng, 1100, bright=30)
    moon, d = _layer()
    d.ellipse((1640, 90, 1860, 310), fill=(255, 246, 210))
    d.ellipse((1700, 70, 1900, 290), fill="black")
    return _finish(_glow(img, moon, 18))


def galaxy_nebula(rng: random.Random) -> Image.Image:
    """Clouds of magenta, cyan and violet gas."""
    img = Image.new("RGB", MAT_SIZE, (6, 4, 16))
    clouds, d = _layer()
    for _ in range(26):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        rx, ry = rng.uniform(120, 380), rng.uniform(60, 200)
        color = rng.choice([(170, 40, 160), (30, 150, 190), (110, 50, 200), (200, 80, 120)])
        d.ellipse((x - rx, y - ry, x + rx, y + ry), fill=color)
    img = ImageChops.screen(img, clouds.filter(ImageFilter.GaussianBlur(70)))
    return _finish(_stars(img, rng, 900, bright=25))


def synthwave_sunset(rng: random.Random) -> Image.Image:
    """Retro sunset over a neon grid."""
    horizon = int(H * 0.52)
    img = Image.new("RGB", MAT_SIZE, (18, 0, 34))
    img.paste(_vgradient((43, 10, 61), (255, 106, 61), (W, horizon)), (0, 0))
    sun, d = _layer()
    cx, r = W // 2, 230
    d.ellipse((cx - r, horizon - r - 40, cx + r, horizon + r - 40), fill=(255, 210, 90))
    for i in range(7):  # the classic stripes across the lower half of the sun
        y = horizon - 40 + i * 26
        d.rectangle((cx - r, y, cx + r, y + 6 + i * 2), fill="black")
    d.rectangle((0, horizon, W, H), fill="black")
    img = _glow(img, sun, 25)
    grid, g = _layer()
    neon = (255, 60, 200)
    for i in range(1, 16):
        y = horizon + (H - horizon) * (i / 15) ** 1.8
        g.line((0, y, W, y), fill=neon, width=3)
    for i in range(-24, 25):
        g.line((cx, horizon, cx + i * 140, H), fill=neon, width=3)
    g.rectangle((0, 0, W, horizon), fill="black")
    return _finish(_glow(img, grid, 6), 0.95)


def ocean_depths(rng: random.Random) -> Image.Image:
    """Rolling waves and rising bubbles."""
    img = _vgradient((10, 108, 140), (3, 28, 58))
    waves, d = _layer()
    for i in range(16):
        pts = _sine_points(30 + i * 46, rng.uniform(8, 22), rng.uniform(280, 520), rng.uniform(0, 6))
        d.line(pts, fill=(80, 200, 230), width=3)
    for _ in range(140):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(3, 14)
        d.ellipse((x - r, y - r, x + r, y + r), outline=(150, 230, 255), width=2)
    return _finish(_glow(img, waves, 5))


def volcano(rng: random.Random) -> Image.Image:
    """Glowing cracks of lava in dark rock."""
    img = _vgradient((32, 8, 6), (14, 4, 3))
    lava, d = _layer()
    for _ in range(40):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        pts = [(x, y)]
        angle = rng.uniform(0, 2 * math.pi)
        for _ in range(rng.randint(8, 22)):
            angle += rng.uniform(-0.7, 0.7)
            x, y = x + 26 * math.cos(angle), y + 26 * math.sin(angle)
            pts.append((x, y))
        d.line(pts, fill=(255, 100, 10), width=rng.randint(3, 7))
    core, c = _layer()
    for _ in range(220):
        x, y, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(1, 3)
        c.ellipse((x - r, y - r, x + r, y + r), fill=(255, 190, 60))
    img = _glow(img, lava, 10)
    return _finish(_glow(img, core, 4))


def enchanted_forest(rng: random.Random) -> Image.Image:
    """Pine silhouettes along both edges, moonlit mist and drifting fireflies."""
    img = _radial((52, 118, 82), (14, 46, 30))
    mist, m = _layer()
    m.ellipse((W * 0.2, H * 0.3, W * 0.8, H * 0.7), fill=(60, 90, 70))
    img = ImageChops.screen(img, mist.filter(ImageFilter.GaussianBlur(120)))
    d = ImageDraw.Draw(img)
    for edge in (0, 1):
        for _ in range(70):
            x, h, w = rng.uniform(-40, W + 40), rng.uniform(90, 210), rng.uniform(40, 80)
            shade = (rng.randint(2, 8), rng.randint(14, 26), rng.randint(8, 16))
            for tier in range(3):
                top = h * (1 - tier / 3.2)
                width = w * (0.6 + tier * 0.35)
                if edge == 0:
                    d.polygon([(x, H - top), (x - width, H - top * 0.45), (x + width, H - top * 0.45)], fill=shade)
                else:
                    d.polygon([(x, top), (x - width, top * 0.45), (x + width, top * 0.45)], fill=shade)
    flies, f = _layer()
    for _ in range(160):
        x, y, r = rng.uniform(0, W), rng.uniform(H * 0.2, H * 0.8), rng.uniform(1.5, 3.5)
        f.ellipse((x - r, y - r, x + r, y + r), fill=(220, 255, 120))
    return _finish(_glow(img, flies, 8))


def arcane_circle(rng: random.Random) -> Image.Image:
    """A golden summoning circle on deep violet."""
    img = _radial((52, 18, 92), (10, 4, 22))
    rune, d = _layer()
    gold = (212, 175, 55)
    cx, cy = W / 2, H / 2
    for r in (330, 300, 220, 130):
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=gold, width=3)
    for k in range(6):  # hexagram
        a1, a2 = math.radians(60 * k - 90), math.radians(60 * k + 30)
        d.line((cx + 300 * math.cos(a1), cy + 300 * math.sin(a1), cx + 300 * math.cos(a2), cy + 300 * math.sin(a2)),
               fill=gold, width=3)
    for k in range(48):  # rune ticks between the outer rings
        a = 2 * math.pi * k / 48
        r1, r2 = 304, 326 if k % 3 else 318
        d.line((cx + r1 * math.cos(a), cy + r1 * math.sin(a), cx + r2 * math.cos(a), cy + r2 * math.sin(a)),
               fill=gold, width=3)
    for side in (-1, 1):  # smaller circles out toward the ends
        for r in (150, 120):
            x = cx + side * 720
            d.ellipse((x - r, cy - r, x + r, cy + r), outline=gold, width=2)
    img = _glow(img, rune, 12)
    return _finish(_stars(img, rng, 250, bright=0))


def aurora(rng: random.Random) -> Image.Image:
    """Northern lights over snowy peaks."""
    img = _vgradient((2, 8, 20), (11, 29, 51))
    img = _stars(img, rng, 700, bright=10)
    lights, d = _layer()
    for color, y0 in (((60, 255, 176), 230), ((54, 198, 255), 300), ((163, 92, 255), 180)):
        pts = _sine_points(y0, rng.uniform(50, 90), rng.uniform(700, 1100), rng.uniform(0, 6), step=16)
        d.line(pts, fill=color, width=60)
    img = _glow(img, lights, 45, keep_sharp=False)
    d = ImageDraw.Draw(img)
    peaks = [(0, H)]
    x = 0.0
    while x < W:
        x += rng.uniform(80, 200)
        peaks.append((x, H - rng.uniform(80, 220)))
    peaks.append((W, H))
    d.polygon(peaks, fill=(4, 12, 22))
    return _finish(img)


def desert_dunes(rng: random.Random) -> Image.Image:
    """Layered dunes under a pale sun."""
    img = _vgradient((240, 200, 130), (150, 92, 45))
    sun, s = _layer()
    s.ellipse((1660, 60, 1820, 220), fill=(255, 245, 205))
    img = _glow(img, sun, 30)
    d = ImageDraw.Draw(img)
    shades = [(214, 160, 92), (196, 140, 72), (178, 120, 58), (160, 102, 46), (140, 86, 38)]
    for i, color in enumerate(shades):
        y0 = 240 + i * 110
        pts = _sine_points(y0, rng.uniform(25, 55), rng.uniform(600, 1000), rng.uniform(0, 6), step=12)
        d.polygon([(0, H), *pts, (W, H)], fill=color)
    return _finish(img, 0.8)


def cherry_blossom(rng: random.Random) -> Image.Image:
    """Dark branches and drifting pink petals."""
    img = _radial((120, 50, 96), (52, 16, 46))
    d = ImageDraw.Draw(img)

    def branch(x: float, y: float, angle: float, length: float, width: float) -> None:
        if length < 18 or width < 1:
            return
        x2, y2 = x + length * math.cos(angle), y + length * math.sin(angle)
        d.line((x, y, x2, y2), fill=(20, 6, 12), width=int(width))
        for turn in (-0.45, 0.4):
            branch(x2, y2, angle + turn + rng.uniform(-0.2, 0.2), length * rng.uniform(0.62, 0.78), width * 0.7)

    for x, y, angle in ((-20, H * 0.12, 0.3), (-20, H * 0.9, -0.35), (W + 20, H * 0.88, math.pi + 0.3),
                        (W + 20, H * 0.1, math.pi - 0.35)):
        branch(x, y, angle, 260, 22)
    petals, p = _layer()
    for _ in range(700):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        rx, ry = rng.uniform(4, 10), rng.uniform(3, 6)
        p.ellipse((x - rx, y - ry, x + rx, y + ry), fill=rng.choice([(255, 183, 213), (255, 140, 190), (250, 210, 230)]))
    return _finish(_glow(img, petals, 3))


def mana_spectrum(rng: random.Random) -> Image.Image:
    """The five colours of mana, blended, with a pip for each."""
    colors = [(248, 243, 214), (14, 104, 171), (60, 50, 48), (211, 32, 42), (0, 115, 62)]
    strip = Image.new("RGB", (len(colors), 1))
    for i, c in enumerate(colors):
        strip.putpixel((i, 0), c)
    img = strip.resize(MAT_SIZE, Image.BILINEAR)
    img = ImageEnhance.Brightness(img).enhance(0.55)
    pips, d = _layer()
    for i, c in enumerate(colors):
        x, y, r = (i + 0.5) * W / 5, H / 2, 110
        d.ellipse((x - r, y - r, x + r, y + r), outline=tuple(min(255, v + 90) for v in c), width=8)
        d.ellipse((x - r * 0.55, y - r * 0.55, x + r * 0.55, y + r * 0.55), fill=c)
    img = _glow(img, pips, 14)
    return _finish(_stars(img, rng, 200, bright=0))


def dragons_hoard(rng: random.Random) -> Image.Image:
    """Heaps of gold coins and gems along the edges."""
    img = _vgradient((34, 20, 8), (20, 12, 6))
    d = ImageDraw.Draw(img)
    for _ in range(900):
        edge = rng.random() < 0.5
        y = rng.triangular(0, H * 0.35, 0) if edge else rng.triangular(H * 0.65, H, H)
        x, r = rng.uniform(0, W), rng.uniform(12, 26)
        gold = rng.choice([(184, 134, 11), (218, 165, 32), (255, 200, 60)])
        d.ellipse((x - r, y - r * 0.7, x + r, y + r * 0.7), fill=gold, outline=(110, 72, 8), width=2)
        d.arc((x - r * 0.6, y - r * 0.45, x + r * 0.6, y + r * 0.45), 200, 330, fill=(255, 240, 170), width=2)
    for _ in range(40):
        x, y, r = rng.uniform(0, W), rng.choice([rng.uniform(0, H * 0.3), rng.uniform(H * 0.7, H)]), rng.uniform(10, 18)
        gem = rng.choice([(200, 20, 40), (20, 160, 80), (40, 90, 220), (150, 40, 200)])
        d.polygon([(x, y - r), (x + r, y), (x, y + r), (x - r, y)], fill=gem, outline=(255, 255, 255))
    return _finish(img, 0.9)


THEMES: dict[str, Callable[[random.Random], Image.Image]] = {
    "Starry Night": starry_night,
    "Galaxy Nebula": galaxy_nebula,
    "Synthwave Sunset": synthwave_sunset,
    "Ocean Depths": ocean_depths,
    "Volcano": volcano,
    "Enchanted Forest": enchanted_forest,
    "Arcane Circle": arcane_circle,
    "Aurora": aurora,
    "Desert Dunes": desert_dunes,
    "Cherry Blossom": cherry_blossom,
    "Mana Spectrum": mana_spectrum,
    "Dragon's Hoard": dragons_hoard,
}


def render(name: str) -> Image.Image:
    """Paints one theme (the same pixels every time)."""
    return THEMES[name](random.Random(name)).convert("RGB")


THUMB_SIZE = (440, 160)  # picture on the in-game playmat picker


IMAGE_TYPES = (".png", ".jpg", ".jpeg", ".webp")


def fit_image(path: Path) -> Image.Image:
    """A picture of any shape on a mat: all of it shown, the leftover filled with its edge colour."""
    with Image.open(path) as src:
        img = src.convert("RGB")
    scale = min(W / img.width, H / img.height)
    img = img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)
    # Fill with the average colour of the edges that get padded (left/right for a narrow picture).
    if img.width < W:
        strips = [img.crop((0, 0, 4, img.height)), img.crop((img.width - 4, 0, img.width, img.height))]
    else:
        strips = [img.crop((0, 0, img.width, 4)), img.crop((0, img.height - 4, img.width, img.height))]
    means = [ImageStat.Stat(strip).mean for strip in strips]
    fill = tuple(round(sum(m[c] for m in means) / len(means)) for c in range(3))
    mat = Image.new("RGB", MAT_SIZE, fill)
    mat.paste(img, ((W - img.width) // 2, (H - img.height) // 2))
    return mat


def custom_mats(folder: Path | None) -> list[tuple[str, Path]]:
    """Pictures dropped in ``folder`` become playmats, named after the file ("Black_Clover.png" -> "Black Clover")."""
    if folder is None or not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.iterdir()):
        if path.suffix.lower() in IMAGE_TYPES:
            name = path.stem.replace("_", " ").replace("-", " ").strip()
            if any(c in name for c in '<>&"'):
                raise ValueError(f"rename {path.name}: playmat names cannot contain < > & or \"")
            out.append((name, path))
    return out


MAT_UNITS = (44.0, 16.0)  # the in-game mat in table units (table.lua MAT_D; the width follows MAT_SIZE)
MAT_MID = 9.5             # its centre's distance from the middle line (table.lua MAT_Z)


def with_zones(img: Image.Image) -> Image.Image:
    """The mat with the zone board's art painted where the board lies, as on the table under it.

    A mat image is drawn as its owner sees it (top toward the middle line), like the table's panels.
    """
    b = zones.BOARD
    px = W / MAT_UNITS[0]
    board = zones.render_board().resize((round(b["w"] * px), round(b["h"] * px)), Image.LANCZOS)
    left = round((b["u"] - b["w"] / 2 + MAT_UNITS[0] / 2) * px)
    top = round((b["d"] - b["h"] / 2 - (MAT_MID - MAT_UNITS[1] / 2)) * px)
    out = img.copy()
    out.paste(board, (left, top))
    return out


def render_all(out_dir: Path, custom_dir: Path | None = None) -> list[tuple[str, str, str]]:
    """Writes every playmat (themes, then pictures from ``custom_dir``) and a thumbnail as hashed JPEGs.

    The mats carry the zone board's art (``with_zones``); the picker's thumbnails show the plain art.
    Returns ``(name, mat filename, thumbnail filename)`` in picker order.
    """
    images = [(name, lambda n=name: render(n)) for name in THEMES]
    images += [(name, lambda p=path: fit_image(p)) for name, path in custom_mats(custom_dir)]
    out = []
    for i, (name, draw) in enumerate(images, 1):
        img = draw()
        mat = save_hashed(with_zones(img), out_dir, f"mat{i:02d}")
        thumb = save_hashed(img.resize(THUMB_SIZE, Image.LANCZOS), out_dir, f"matthumb{i:02d}")
        out.append((name, mat, thumb))
    return out
