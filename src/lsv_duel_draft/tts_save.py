"""Assemble the Tabletop Simulator save file (JSON) for the duel draft table."""

from __future__ import annotations

from datetime import datetime
from importlib import resources
from typing import Any

from lsv_duel_draft.models import Card, Sheet, SheetSlot
from lsv_duel_draft.sheets import COLS, PER_SHEET, ROWS

SAVE_NAME = "LSV Cube Duel Draft"
FRONT_SHEET_BASE = 1
BACK_SHEET_BASE = 51
CUBE_GUID = "c00001"
HAND_GUIDS = {"White": "a00001", "Red": "a00002"}


def assign_slots(cards: list[Card]) -> tuple[list[SheetSlot], list[SheetSlot | None]]:
    """Place every front face, then every back face, onto numbered sheets."""
    fronts = [SheetSlot(FRONT_SHEET_BASE + i // PER_SHEET, i % PER_SHEET) for i in range(len(cards))]
    backs: list[SheetSlot | None] = []
    n = 0
    for card in cards:
        if card.back is None:
            backs.append(None)
        else:
            backs.append(SheetSlot(BACK_SHEET_BASE + n // PER_SHEET, n % PER_SHEET))
            n += 1
    return fronts, backs


def _transform(x: float = 0, y: float = 1, z: float = 0, ry: float = 0, rz: float = 0,
               sx: float = 1, sy: float = 1, sz: float = 1) -> dict[str, float]:
    return {"posX": x, "posY": y, "posZ": z, "rotX": 0, "rotY": ry, "rotZ": rz,
            "scaleX": sx, "scaleY": sy, "scaleZ": sz}


def _deck_entry(sheet: Sheet, back_url: str) -> dict[str, Any]:
    return {"FaceURL": sheet.url, "BackURL": back_url, "NumWidth": COLS, "NumHeight": ROWS,
            "BackIsHidden": True, "UniqueBack": False, "Type": 0}


def _card_object(guid: str, name: str, text: str, note: str, slot: SheetSlot,
                 sheets: dict[int, Sheet], back_url: str) -> dict[str, Any]:
    return {
        "GUID": guid,
        "Name": "Card",
        "Transform": _transform(rz=180),
        "Nickname": name,
        "Description": text,
        "GMNotes": note,
        "CardID": slot.card_id,
        "CustomDeck": {str(slot.sheet_id): _deck_entry(sheets[slot.sheet_id], back_url)},
        "HideWhenFaceDown": True,
        "Hands": True,
        "Tooltip": True,
    }


def build_cube_deck(cards: list[Card], sheets: dict[int, Sheet], back_url: str) -> dict[str, Any]:
    """The face-down cube deck; double-faced cards carry their back as state 2."""
    fronts, backs = assign_slots(cards)
    contained = []
    for i, (card, front, back) in enumerate(zip(cards, fronts, backs, strict=True)):
        obj = _card_object(f"{0xd00000 + i:06x}", card.front.name, card.front.text,
                           card.scryfall_id, front, sheets, back_url)
        if card.back is not None and back is not None:
            obj["States"] = {"2": _card_object(f"{0xe00000 + i:06x}", card.back.name, card.back.text,
                                               card.scryfall_id, back, sheets, back_url)}
        contained.append(obj)
    return {
        "GUID": CUBE_GUID,
        "Name": "Deck",
        "Transform": _transform(x=-6, y=1.2, ry=180, rz=180),
        "Nickname": "LSV Cube",
        "Description": f"{len(cards)} cards",
        "DeckIDs": [s.card_id for s in fronts],
        "CustomDeck": {str(s.sheet_id): _deck_entry(s, back_url)
                       for s in sheets.values() if s.sheet_id < BACK_SHEET_BASE},
        "ContainedObjects": contained,
        "HideWhenFaceDown": True,
        "Hands": False,
    }


def _zones() -> list[dict[str, Any]]:
    """Hand zones for both seats (the Lua script moves them to fit the table).

    Picks are kept private per card with ``setInvisibleTo`` rather than with
    hidden zones, which TTS renders as solid colored blocks.
    """
    return [
        {"GUID": HAND_GUIDS[color], "Name": "HandTrigger", "FogColor": color,
         "Transform": _transform(z=sign * 19, y=4, ry=0 if sign < 0 else 180, sx=24, sy=5, sz=4)}
        for color, sign in (("White", -1), ("Red", 1))
    ]


def global_lua() -> str:
    """The Global script: rules engine followed by the table adapter."""
    pkg = resources.files("lsv_duel_draft") / "lua"
    return (pkg / "draft_core.lua").read_text(encoding="utf-8") + "\n" + (pkg / "table.lua").read_text(encoding="utf-8")


def global_xml() -> str:
    """The Global UI (status bar, start button, per-seat pick prompts)."""
    return (resources.files("lsv_duel_draft") / "lua" / "ui.xml").read_text(encoding="utf-8")


def build_save(cards: list[Card], sheets: dict[int, Sheet], back_url: str, cube_name: str) -> dict[str, Any]:
    """The complete save: table, zones, cube deck, scripts and UI."""
    return {
        "SaveName": SAVE_NAME,
        "GameMode": SAVE_NAME,
        "Date": datetime.now().strftime("%m/%d/%Y %I:%M:%S %p"),
        "VersionNumber": "",
        "GameType": "Card Game",
        "GameComplexity": "",
        "Tags": [],
        "Gravity": 0.5,
        "PlayArea": 0.5,
        "Table": "Table_RPG",
        "Sky": "Sky_Museum",
        "Note": f"1v1 pick-from-4 draft of {cube_name}. Sit at White and Red, then press Start Draft.",
        "Rules": "",
        "TabStates": {},
        "Hands": {"Enable": True, "DisableUnused": False, "Hiding": 0},
        "LuaScript": global_lua(),
        "LuaScriptState": "",
        "XmlUI": global_xml(),
        "ObjectStates": [*_zones(), build_cube_deck(cards, sheets, back_url)],
    }
