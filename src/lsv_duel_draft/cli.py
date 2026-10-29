"""`uv run lsv-duel-draft` — build the card sheets and the Tabletop Simulator save.

Steps: CubeCobra list -> Scryfall data and images -> deck sheets in ``sheets/``
-> save JSON in ``dist/`` (and in the Tabletop Simulator Saves folder if it exists).
With ``--push`` the sheets are committed and pushed so the save's image URLs resolve.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from lsv_duel_draft import sheets as sh
from lsv_duel_draft.models import Card, Sheet
from lsv_duel_draft.sources import (
    MAGIC_CARD_BACK,
    download_image,
    fetch_cards,
    fetch_cube_ids,
    make_client,
)
from lsv_duel_draft.tts_save import (
    BACK_SHEET_BASE,
    FRONT_SHEET_BASE,
    SAVE_NAME,
    build_save,
)

ROOT = Path(__file__).resolve().parents[2]
SHEETS_DIR = ROOT / "sheets"
CACHE_DIR = ROOT / ".cache" / "images"
DIST_DIR = ROOT / "dist"


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


def render_all(cards: list[Card], images: dict[str, Path], slug: str, branch: str) -> tuple[dict[int, Sheet], str]:
    """Render front sheets, back-face sheets and the card back; return sheets by id and the back URL."""
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

    back_name = sh.save_hashed(sh.card_back(images[MAGIC_CARD_BACK]), SHEETS_DIR, "cardback")
    written.add(back_name)

    for old in SHEETS_DIR.glob("*.jpg"):
        if old.name not in written:
            old.unlink()
    return sheets, raw_url(slug, branch, back_name)


def push_sheets(cube: str) -> None:
    """Commit and push the sheets folder (no-op when nothing changed)."""
    _git("add", "-A", "sheets")
    if not _git("status", "--porcelain", "sheets"):
        print("Sheets unchanged; nothing to push.")
        return
    _git("commit", "-m", f"Update card sheets for {cube}")
    _git("push", "origin", "HEAD")
    print("Pushed sheets to GitHub.")


def main(argv: list[str] | None = None) -> None:
    """Build everything for one cube."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cube", default="LSVCube", help="CubeCobra cube id (default: LSVCube)")
    parser.add_argument("--branch", default="main", help="branch the sheets are served from")
    parser.add_argument("--push", action="store_true", help="commit and push the sheets after building")
    args = parser.parse_args(argv)

    slug = repo_slug()
    with make_client() as client:
        ids, basic_ids = fetch_cube_ids(client, args.cube)
        print(f"{args.cube}: {len(ids)} cards, {len(basic_ids)} basic lands")
        cards = fetch_cards(client, ids)
        basics = fetch_cards(client, basic_ids)
        everything = cards + basics
        urls = list(dict.fromkeys([c.front.image_url for c in everything]
                                  + [c.back.image_url for c in everything if c.back] + [MAGIC_CARD_BACK]))
        images: dict[str, Path] = {}
        for n, url in enumerate(urls, 1):
            images[url] = download_image(client, url, CACHE_DIR)
            if n % 50 == 0 or n == len(urls):
                print(f"  images {n}/{len(urls)}")

    # Basics go on the front sheets after the cube's cards (see tts_save.build_save).
    sheets, back_url = render_all(everything, images, slug, args.branch)
    dfc = sum(1 for c in cards if c.back)
    print(f"Rendered {len(sheets)} sheets ({dfc} double-faced cards).")

    save = build_save(cards, sheets, back_url, args.cube, basics)
    DIST_DIR.mkdir(exist_ok=True)
    out = DIST_DIR / f"{SAVE_NAME}.json"
    out.write_text(json.dumps(save, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {out}")
    for saves in tts_saves_dirs():
        saves.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out, saves / out.name)
        print(f"Installed to {saves / out.name}")
    if not tts_saves_dirs():
        print("Tabletop Simulator's Saves folder was not found; launch the game once, then rerun "
              f"or copy {out.name} into Documents/My Games/Tabletop Simulator/Saves.")

    if args.push:
        push_sheets(args.cube)
