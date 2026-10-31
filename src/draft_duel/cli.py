"""`uv run draft-duel` — build the card sheets and the Draft Duel Tabletop Simulator saves.

Steps: each cube's list (CubeCobra, or MTGO's Vintage Cube page) -> Scryfall data
and images -> deck sheets in ``sheets/`` -> save JSON in ``dist/`` (and in the
Tabletop Simulator Saves folder if it exists). Players pick the cube in game.
Two saves share the sheets: "Draft Duel" (1v1) and "Draft Duel 4P" (the
four-player queue draft, with its own table image and narrower playmats).
With ``--push`` the sheets are committed and pushed so the save's image URLs resolve.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from draft_duel import playmats, props, tabletop, zones
from draft_duel import sheets as sh
from draft_duel.cubes import CUBES, DEFAULT_CUBES, load_cube, resolve
from draft_duel.models import Card, Cube, Sheet, Token
from draft_duel.seats import DUEL, FOUR
from draft_duel.sources import (
    CARD_SWAPS,
    MAGIC_CARD_BACK,
    download_image,
    fetch_cards_by_name,
    make_client,
    swap_cards,
)

BASIC_NAMES = ["Plains", "Island", "Swamp", "Mountain", "Forest"]
from draft_duel.tokens import load_tokens, match_makers, token_faces
from draft_duel.tts_save import (
    BACK_SHEET_BASE,
    FRONT_SHEET_BASE,
    TOKEN_SHEET_BASE,
    build_save,
    deck_entry,
)

ROOT = Path(__file__).resolve().parents[2]
SHEETS_DIR = ROOT / "sheets"
CACHE_DIR = ROOT / ".cache" / "images"
DIST_DIR = ROOT / "dist"
PLAYMATS_DIR = ROOT / "playmats"  # drop pictures here to add them as playmats


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def repo_slug() -> str:
    """``owner/name`` of the ``origin`` GitHub remote."""
    url = _git("remote", "get-url", "origin")
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    if not m:
        raise SystemExit(f"origin is not a GitHub remote: {url}")
    return m.group(1)


def raw_url(slug: str, branch: str, filename: str) -> str:
    """Public URL Tabletop Simulator loads a sheet from."""
    return f"https://raw.githubusercontent.com/{slug}/{branch}/sheets/{filename}"


def tts_saves_dirs() -> list[Path]:
    """Existing Tabletop Simulator Saves folders (OneDrive-redirected Documents included)."""
    home = Path.home()
    candidates = [home / "OneDrive" / "Documents", home / "Documents"]
    return [d / "My Games" / "Tabletop Simulator" / "Saves" for d in candidates
            if (d / "My Games" / "Tabletop Simulator").is_dir()]


@dataclass
class Rendered:
    """Everything ``render_all`` drew, as the saves need it (URLs on the repo)."""

    sheets: dict[int, Sheet]
    back_url: str
    mats: list[dict[str, str]]          # 1v1 playmats: name, url, thumb
    mats_4p: list[dict[str, str]]       # the same mats for the four-player table's narrower quarters
    zones_url: str
    table_url: str
    table_4p_url: str
    prop_token_urls: dict[str, str]


def render_all(cards: list[Card], images: dict[str, Path], slug: str, branch: str,
               tokens: list[Token] | None = None, prop_faces: list[str] | None = None,
               prop_tokens: list[str] | None = None) -> Rendered:
    """Render card, token, playmat, zone-board, table and prop images for both saves."""
    SHEETS_DIR.mkdir(exist_ok=True)
    sheets: dict[int, Sheet] = {}
    written: set[str] = set()

    def add(sheet_id: int, faces: list[str], prefix: str) -> None:
        name = sh.save_hashed(sh.render_sheet([images[u] for u in faces]), SHEETS_DIR, prefix)
        written.add(name)
        sheets[sheet_id] = Sheet(sheet_id, name, raw_url(slug, branch, name))

    for i, group in enumerate(sh.chunk([c.front.image_url for c in cards])):
        add(FRONT_SHEET_BASE + i, group, f"front{i + 1:02d}")
    for i, group in enumerate(sh.chunk([c.back.image_url for c in cards if c.back])):
        add(BACK_SHEET_BASE + i, group, f"back{i + 1:02d}")
    for i, group in enumerate(sh.chunk(token_faces(tokens or []))):
        add(TOKEN_SHEET_BASE + i, group, f"tokens{i + 1:02d}")
    for i, group in enumerate(sh.chunk(prop_faces or [])):
        add(props.PROP_SHEET_BASE + i, group, f"props{i + 1:02d}")
    prop_token_urls: dict[str, str] = {}
    for i, url in enumerate(prop_tokens or [], 1):
        with Image.open(images[url]) as img:
            img = img.convert("RGBA")
            img.thumbnail((488, 680), Image.LANCZOS)  # Scryfall's "normal" size
            name = sh.save_hashed_png(img, SHEETS_DIR, f"proptoken{i:02d}")
        written.add(name)
        prop_token_urls[url] = raw_url(slug, branch, name)

    back_name = sh.save_hashed(sh.card_back(images[MAGIC_CARD_BACK]), SHEETS_DIR, "cardback")
    written.add(back_name)
    mats = []
    for name, filename, thumb in playmats.render_all(SHEETS_DIR, PLAYMATS_DIR):
        written.update((filename, thumb))
        mats.append({"name": name, "url": raw_url(slug, branch, filename), "thumb": raw_url(slug, branch, thumb)})
    mats_4p = []
    for mat, (name, filename) in zip(mats, playmats.render_narrow(SHEETS_DIR, FOUR.mat_w, PLAYMATS_DIR), strict=True):
        written.add(filename)
        mats_4p.append({**mat, "name": name, "url": raw_url(slug, branch, filename)})

    zones_name = zones.render_all(SHEETS_DIR)
    table_name = tabletop.render_all(SHEETS_DIR, DUEL)
    table_4p_name = tabletop.render_all(SHEETS_DIR, FOUR)
    written.update((zones_name, table_name, table_4p_name))

    for old in [*SHEETS_DIR.glob("*.jpg"), *SHEETS_DIR.glob("*.png")]:
        if old.name not in written:
            old.unlink()
    return Rendered(sheets, raw_url(slug, branch, back_name), mats, mats_4p, raw_url(slug, branch, zones_name),
                    raw_url(slug, branch, table_name), raw_url(slug, branch, table_4p_name), prop_token_urls)


def push_sheets(cube: str) -> None:
    """Commit and push the sheets folder (no-op when nothing changed)."""
    _git("add", "-A", "sheets")
    if not _git("status", "--porcelain", "sheets"):
        print("Sheets unchanged; nothing to push.")
        return
    _git("commit", "-m", f"Update card sheets for {cube}")
    _git("push", "origin", "HEAD")
    print("Pushed sheets to GitHub.")


def unpublished_sheets(branch: str, sheets_dir: Path = SHEETS_DIR) -> list[str]:
    """Images in the sheets folder that ``origin/<branch>`` lacks. Names carry a content hash, so a name
    on the branch means the same image is there; TTS shows a missing one as blank white cards."""
    try:
        published = _git("ls-tree", "--name-only", f"origin/{branch}", "sheets/").splitlines()
    except subprocess.CalledProcessError:
        published = []
    names = {Path(p).name for p in published}
    return sorted(p.name for p in sheets_dir.iterdir() if p.is_file() and p.name not in names)


def main(argv: list[str] | None = None) -> None:
    """Build one save offering every selected cube."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cubes", default=",".join(DEFAULT_CUBES),
                        help=f"comma-separated cubes, the first is on the table at load: {', '.join(CUBES)} "
                             f"or cubecobra:<id> (default: {','.join(DEFAULT_CUBES)})")
    parser.add_argument("--branch", default="main", help="branch the sheets are served from")
    parser.add_argument("--push", action="store_true", help="commit and push the sheets after building")
    args = parser.parse_args(argv)
    try:
        sources = [resolve(s.strip()) for s in args.cubes.split(",") if s.strip()]
    except ValueError as exc:
        parser.error(str(exc))
    if not sources or len({s.key for s in sources}) != len(sources):
        parser.error("--cubes needs at least one cube and no repeats")

    slug = repo_slug()
    with make_client() as client:
        replacements = fetch_cards_by_name(client, list(CARD_SWAPS.values()))
        swaps = {old: replacements[new] for old, new in CARD_SWAPS.items()}
        cubes: list[Cube] = []
        basics: list[Card] = []
        for source in sources:
            cube_cards, cube_basics = load_cube(client, source)
            cube_cards, absent = swap_cards(cube_cards, swaps)
            print(f"{source.name}: {len(cube_cards)} cards")
            for old, new in CARD_SWAPS.items():
                if old not in absent:
                    print(f"  {old} -> {new}")
            cubes.append(Cube(source.key, source.name, cube_cards))
            basics = basics or cube_basics  # the first cube that lists basics provides them
        if not basics:
            by_name = fetch_cards_by_name(client, BASIC_NAMES)
            basics = [by_name[n] for n in BASIC_NAMES]
        cards = [c for cube in cubes for c in cube.cards]
        everything = cards + basics
        tokens, makers, missing = match_makers(load_tokens(), cards)
        print(f"Tokens: {len(tokens)} made by {len(makers)} cube cards")
        if missing:
            print(f"  in no cube (check data/tokens.csv): {', '.join(missing)}")
        table_props = props.load_props(props.workshop_file())
        prop_faces = props.card_faces(table_props)
        prop_tokens = props.token_images(table_props)
        urls = list(dict.fromkeys([c.front.image_url for c in everything]
                                  + [c.back.image_url for c in everything if c.back]
                                  + token_faces(tokens) + prop_faces + prop_tokens + [MAGIC_CARD_BACK]))
        images: dict[str, Path] = {}
        for n, url in enumerate(urls, 1):
            images[url] = download_image(client, url, CACHE_DIR)
            if n % 50 == 0 or n == len(urls):
                print(f"  images {n}/{len(urls)}")

    # Cubes' cards fill the front sheets in order, then the basics (see tts_save.build_save).
    r = render_all(everything, images, slug, args.branch, tokens, prop_faces, prop_tokens)
    sheets, back_url = r.sheets, r.back_url
    dfc = sum(1 for c in cards if c.back)
    print(f"Rendered {len(sheets)} sheets ({dfc} double-faced cards) and {len(r.mats)} playmats.")

    if table_props:
        prop_sheets = {sid: deck_entry(sheet, back_url) for sid, sheet in sheets.items() if sid >= props.PROP_SHEET_BASE}
        table_props = props.rehost(table_props, prop_faces, prop_sheets, sh.PER_SHEET)
        table_props = props.rehost_tokens(table_props, r.prop_token_urls)
        print(f"Added {len(table_props)} table props from the MTG EDH mod ({len(prop_faces)} card and "
              f"{len(prop_tokens)} token images rehosted).")
    else:
        print(f"Table props skipped: subscribe to the MTG EDH table (Workshop {props.WORKSHOP_ID}) and load it once.")
    DIST_DIR.mkdir(exist_ok=True)
    for table, mats, table_url in ((DUEL, r.mats, r.table_url), (FOUR, r.mats_4p, r.table_4p_url)):
        save = build_save(cubes, sheets, back_url, basics, tokens, makers, mats, r.zones_url, table_url,
                          table_props, table)
        out = DIST_DIR / f"{table.name}.json"
        out.write_text(json.dumps(save, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {out}")
        for saves in tts_saves_dirs():
            saves.mkdir(parents=True, exist_ok=True)
            shutil.copy2(out, saves / out.name)
            print(f"Installed to {saves / out.name}")
    if not tts_saves_dirs():
        print("Tabletop Simulator's Saves folder was not found; launch the game once, then rerun "
              f"or copy the saves in {DIST_DIR} into Documents/My Games/Tabletop Simulator/Saves.")

    if args.push:
        push_sheets(" + ".join(c.name for c in cubes))
    elif missing_sheets := unpublished_sheets(args.branch):
        print(f"WARNING: {len(missing_sheets)} image(s) this save uses are not on origin/{args.branch}, so "
              "they load blank white in game until pushed (rerun with --push):")
        for name in missing_sheets:
            print(f"  sheets/{name}")
