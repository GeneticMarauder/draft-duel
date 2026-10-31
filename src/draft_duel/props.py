"""Table props borrowed from the MTG EDH table (Steam Workshop 2425949312).

The props sit on the wooden ends of the custom table, where players drag what
they need onto the board: mana counters, keyword markers and counter tokens on
the left end; d20 / d10 / d6 and coin bags on the right; a black-hole bin in
each corner (click it to open; whatever falls in is deleted); and on the right
end the emblem deck, a deck of extra cards (The Monarch, Day, Experience…) and the
dungeon cards. Our table is the same custom table, so they keep the EDH positions.

Those cards' images were on Scryfall: one retired host (c1.scryfall.com) and one
that refuses TTS's downloads. ``card_faces`` lists them on Scryfall's current host
so the build downloads them like cube cards and renders them onto our own sheets
(``PROP_SHEET_BASE`` up); ``rehost`` points every card at its slot on those sheets.

They are other people's Workshop objects, so they are not copied into this repo:
each build reads them from the player's downloaded copy of the EDH mod, and
builds without them when it is not there. Left out on purpose: the card
importers and other web-fetching tools, EDH-only counters (commander damage,
turns) and the playmat bag.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

WORKSHOP_ID = "2425949312"

PROP_GUIDS: dict[str, list[str]] = {
    "mana counters": ["cd8bb6", "4783af", "cdbccc", "220d2f", "1c4a59", "aeeb11", "9360fc"],
    "keyword markers": ["78d2d4", "55627e", "6fd72d", "dfa623", "5489a1", "6abc8c", "81386a", "3790a3",
                        "f31df3", "e59538", "231bdf", "6e26dc", "18889c", "5e33ad", "5e4d3f", "1bec7e"],
    "counter tokens": ["81ae86", "b86992", "1ea882", "242285", "328fa7", "496e64", "cb11d3", "164e47",
                       "f2a0d2", "967fea", "d3fa4f", "cc8fbc", "2c18ff", "b39e2f", "87df9c", "5fe4e6"],
    "dice and coins": ["40f121", "eaf0c1", "c82e0f", "6467a8"],
    "black holes": ["30f2bd", "0a09ad", "cf6ca1", "95e9ee"],
    "extra cards": ["d40d7e", "946716", "a87f74"],   # emblems deck, extra-cards deck, dungeon bag
}
PROP_SHEET_BASE = 71       # after the card (1+), token (41+) and back (51+) sheets
OLD_SCRYFALL = "https://c1.scryfall.com/file/scryfall-cards/"
SCRYFALL = "https://cards.scryfall.io/"


def workshop_file(home: Path | None = None) -> Path | None:
    """The downloaded EDH mod's save, if Tabletop Simulator has it (OneDrive-redirected Documents too)."""
    home = home or Path.home()
    for docs in (home / "OneDrive" / "Documents", home / "Documents"):
        path = docs / "My Games" / "Tabletop Simulator" / "Mods" / "Workshop" / f"{WORKSHOP_ID}.json"
        if path.is_file():
            return path
    return None


def load_props(path: Path | None) -> list[dict[str, Any]]:
    """The props from the EDH save at ``path`` (copies, all locked); empty when there is no file.

    Raises ``KeyError`` naming any prop the save no longer has (the mod was updated).
    """
    if path is None or not path.is_file():
        return []
    objects = {o["GUID"]: o for o in json.loads(path.read_text(encoding="utf-8"))["ObjectStates"]}
    wanted = [g for guids in PROP_GUIDS.values() for g in guids]
    missing = [g for g in wanted if g not in objects]
    if missing:
        raise KeyError(f"the EDH mod no longer has props {missing}; update props.PROP_GUIDS")
    props = []
    for guid in wanted:
        obj = copy.deepcopy(objects[guid])
        obj["Locked"] = True
        props.append(obj)
    return props


def _guids(obj: dict[str, Any]) -> list[str]:
    out = [obj.get("GUID", "")]
    for child in obj.get("ContainedObjects") or []:
        out += _guids(child)
    return out


def merge(objects: list[dict[str, Any]], props: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """``objects`` plus ``props``, giving any prop (or its contents) a fresh GUID if it would collide."""
    taken = {g for o in objects for g in _guids(o)}
    out = list(objects)
    n = 0
    for prop in props:
        prop = copy.deepcopy(prop)
        stack = [prop]
        while stack:
            obj = stack.pop()
            if obj.get("GUID") in taken:
                while f"e{n:05x}" in taken:
                    n += 1
                obj["GUID"] = f"e{n:05x}"
            taken.add(obj.get("GUID", ""))
            stack.extend(obj.get("ContainedObjects") or [])
        out.append(prop)
    return out


def _cards(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Every card inside ``obj`` (itself too, if it is a card, and other faces of double-faced cards)."""
    out = [obj] if obj.get("Name") in ("Card", "CardCustom") and obj.get("CustomDeck") else []
    for child in [*(obj.get("ContainedObjects") or []), *(obj.get("States") or {}).values()]:
        out += _cards(child)
    return out


def _tokens(obj: dict[str, Any]) -> list[dict[str, Any]]:
    """Every object inside ``obj`` (itself too) drawn from a single custom image."""
    out = [obj] if obj.get("CustomImage", {}).get("ImageURL") else []
    for child in obj.get("ContainedObjects") or []:
        out += _tokens(child)
    return out


def token_images(props: list[dict[str, Any]]) -> list[str]:
    """Scryfall images that custom tokens (poison, experience, energy counters) are cut from.

    They stay single PNGs, not sheet slots: a token's shape comes from the image's transparency.
    """
    urls = []
    for prop in props:
        for tok in _tokens(prop):
            url = current_url(tok["CustomImage"]["ImageURL"])
            if url.startswith(SCRYFALL) and url not in urls:
                urls.append(url)
    return urls


def rehost_tokens(props: list[dict[str, Any]], hosted: dict[str, str]) -> list[dict[str, Any]]:
    """Copies of ``props`` whose custom tokens use ``hosted[scryfall url]`` instead of Scryfall."""
    out = []
    for prop in props:
        prop = copy.deepcopy(prop)
        for tok in _tokens(prop):
            url = current_url(tok["CustomImage"]["ImageURL"])
            if url in hosted:
                tok["CustomImage"]["ImageURL"] = hosted[url]
        out.append(prop)
    return out


def current_url(url: str) -> str:
    """A Scryfall image URL on Scryfall's current host (the retired c1 host maps one to one)."""
    if url.startswith(OLD_SCRYFALL):
        url = SCRYFALL + url[len(OLD_SCRYFALL):]
    return url


def card_faces(props: list[dict[str, Any]]) -> list[str]:
    """The Scryfall images of every card in the props, deduplicated, in sheet order."""
    faces = []
    for prop in props:
        for card in _cards(prop):
            for entry in card["CustomDeck"].values():
                url = current_url(entry["FaceURL"])
                if url.startswith(SCRYFALL) and url not in faces:
                    faces.append(url)
    return faces


def rehost(props: list[dict[str, Any]], faces: list[str], sheet_entry: dict[int, dict[str, Any]],
           per_sheet: int) -> list[dict[str, Any]]:
    """Copies of ``props`` whose Scryfall cards use our sheets: face ``i`` of ``faces`` is slot
    ``i % per_sheet`` of sheet ``PROP_SHEET_BASE + i // per_sheet``, whose ``CustomDeck`` entry is
    ``sheet_entry[sheet id]``. Decks get matching ``DeckIDs`` and ``CustomDeck``."""
    where = {url: (PROP_SHEET_BASE + i // per_sheet, i % per_sheet) for i, url in enumerate(faces)}
    out = []
    for prop in props:
        prop = copy.deepcopy(prop)
        for card in _cards(prop):
            url = current_url(next(iter(card["CustomDeck"].values()))["FaceURL"])
            if url in where:
                sheet, slot = where[url]
                card["CardID"] = sheet * 100 + slot
                card["CustomDeck"] = {str(sheet): sheet_entry[sheet]}
        stack = [prop]
        while stack:
            obj = stack.pop()
            if obj.get("Name") == "Deck":
                cards = obj.get("ContainedObjects") or []
                obj["DeckIDs"] = [c["CardID"] for c in cards]
                obj["CustomDeck"] = {k: v for c in cards for k, v in c["CustomDeck"].items()}
            stack.extend(obj.get("ContainedObjects") or [])
        out.append(prop)
    return out
