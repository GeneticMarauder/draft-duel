"""Assemble the Tabletop Simulator save file (JSON) for the duel draft table."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from importlib import resources
from typing import Any

from lsv_duel_draft.models import Card, Sheet, SheetSlot, Token
from lsv_duel_draft.sheets import COLS, PER_SHEET, ROWS
from lsv_duel_draft.tokens import token_faces

SAVE_NAME = "LSV Cube Duel Draft"
FRONT_SHEET_BASE = 1
TOKEN_SHEET_BASE = 41
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


def card_note(card: Card, basic: bool = False) -> str:
    """GMNotes payload the deck editor reads: id, mana value, land and basic-land flags."""
    return json.dumps({"id": card.scryfall_id, "cmc": card.cmc, "land": card.is_land, "basic": basic})


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
        "Sticky": False,  # picking a card up never drags the cards resting on it
    }


def build_cube_deck(cards: list[Card], fronts: Sequence[SheetSlot], backs: Sequence[SheetSlot | None],
                    sheets: dict[int, Sheet], back_url: str) -> dict[str, Any]:
    """The face-down cube deck; double-faced cards carry their back as state 2."""
    contained = []
    for i, (card, front, back) in enumerate(zip(cards, fronts, backs, strict=True)):
        note = card_note(card)
        obj = _card_object(f"{0xd00000 + i:06x}", card.front.name, card.front.text, note, front, sheets, back_url)
        if card.back is not None and back is not None:
            obj["States"] = {"2": _card_object(f"{0xe00000 + i:06x}", card.back.name, card.back.text,
                                               note, back, sheets, back_url)}
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


def basic_land_objects(basics: list[Card], slots: Sequence[SheetSlot], sheets: dict[int, Sheet],
                       back_url: str) -> list[dict[str, Any]]:
    """One card object per basic land, for the deck editor's bottomless land bags."""
    return [
        _card_object(f"{0xf00000 + i:06x}", b.front.name, b.front.text, card_note(b, basic=True),
                     slot, sheets, back_url)
        for i, (b, slot) in enumerate(zip(basics, slots, strict=True))
    ]


def assign_token_slots(tokens: list[Token]) -> list[tuple[SheetSlot, SheetSlot | None]]:
    """(front, back) slot per token on the token sheets, in :func:`token_faces` order."""
    slots = [SheetSlot(TOKEN_SHEET_BASE + i // PER_SHEET, i % PER_SHEET)
             for i in range(len(token_faces(tokens)))]
    out: list[tuple[SheetSlot, SheetSlot | None]] = []
    n_backs = 0
    for i, token in enumerate(tokens):
        back = None
        if token.back_url:
            back = slots[len(tokens) + n_backs]
            n_backs += 1
        out.append((slots[i], back))
    return out


def token_objects(tokens: list[Token], sheets: dict[int, Sheet], back_url: str) -> dict[str, dict[str, Any]]:
    """Spawnable card data per token label; double-faced tokens carry their back as state 2.

    GMNotes ``{"token": label}`` lets the script find a token it made (and
    keeps tokens out of the deck editor, which looks for ``id``).
    """
    out = {}
    for i, (token, (front, back)) in enumerate(zip(tokens, assign_token_slots(tokens), strict=True)):
        note = json.dumps({"token": token.label})
        obj = _card_object(f"{0xa10000 + i:06x}", token.label, token.text, note, front, sheets, back_url)
        if back is not None:
            obj["States"] = {"2": _card_object(f"{0xa20000 + i:06x}", token.label, token.text, note,
                                               back, sheets, back_url)}
        out[token.label] = obj
    return out


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


def global_lua(basic_lands: list[dict[str, Any]] | None = None,
               tokens: dict[str, Any] | None = None,
               mats: list[dict[str, str]] | None = None) -> str:
    """The Global script: basic-land, token and playmat data, rules engine, then the table adapter.

    ``tokens`` is ``{"tokens": {label: card data}, "makers": {card id: [label, ...]}}``;
    ``mats`` is ``[{"name": ..., "url": ...}, ...]``.
    """
    pkg = resources.files("lsv_duel_draft") / "lua"
    lands_json = json.dumps(basic_lands or [])
    tokens_json = json.dumps(tokens or {"tokens": {}, "makers": {}})
    mats_json = json.dumps(mats or [])
    if "]==]" in lands_json + tokens_json + mats_json:
        raise ValueError("card text would end the Lua long string early")
    header = (f"BASIC_LANDS_JSON = [==[{lands_json}]==]\nTOKENS_JSON = [==[{tokens_json}]==]\n"
              f"MATS_JSON = [==[{mats_json}]==]\n")
    return (header + (pkg / "draft_core.lua").read_text(encoding="utf-8") + "\n"
            + (pkg / "table.lua").read_text(encoding="utf-8"))


def _mat_cell(color: str, index: int, name: str, image: str | None) -> str:
    """One picker cell: a thumbnail button (index 0 = no playmat) and the mat's name."""
    if image:
        button = (f'<Button id="matPick_{color}_{index}" onClick="onMatPick" image="{image}" preferredHeight="84" '
                  'colors="#FFFFFF|#E0E0E0|#BDBDBD|#555555"></Button>')
    else:
        button = (f'<Button id="matPick_{color}_{index}" onClick="onMatPick" preferredHeight="84" fontSize="18" '
                  'textColor="#FFFFFF" colors="#37474F|#455A64|#263238|#555555">No playmat</Button>')
    return (f'<Panel><VerticalLayout spacing="2">{button}'
            f'<Text preferredHeight="24" fontSize="15" color="#FFFFFF">{name}</Text></VerticalLayout></Panel>')


def mat_pickers(mats: Sequence[dict[str, str]]) -> str:
    """Per-seat playmat pickers: a mid-screen grid of thumbnails, shown only to that seat.

    Thumbnail ``i`` (1-based, ``MATS_JSON`` order) is the custom UI asset ``matthumb<i>``.
    """
    if any(c in m["name"] for m in mats for c in '<>&"'):
        raise ValueError("playmat names must not need XML escaping (TTS shows entities literally)")
    panels = []
    for color in ("White", "Red"):
        cells = [_mat_cell(color, 0, "None", None)]
        cells += [_mat_cell(color, i, m["name"], f"matthumb{i}") for i, m in enumerate(mats, 1)]
        panels.append(
            f'<Panel id="matPicker_{color}" visibility="{color}" active="false" rectAlignment="MiddleCenter" '
            'width="1000" height="600" color="#101018F2">'
            '<VerticalLayout padding="16 16 12 16" spacing="10">'
            '<HorizontalLayout preferredHeight="36" spacing="10">'
            '<Text fontSize="22" color="#FFFFFF" alignment="MiddleLeft">Choose your playmat</Text>'
            f'<Button id="matClose_{color}" preferredWidth="110" fontSize="16" onClick="onMatButton" '
            'textColor="#FFFFFF" colors="#37474F|#455A64|#263238|#555555">Close</Button>'
            '</HorizontalLayout>'
            '<GridLayout cellSize="230 112" spacing="10 10" constraint="FixedColumnCount" constraintCount="4">'
            + "".join(cells) + '</GridLayout></VerticalLayout></Panel>')
    return "\n".join(panels)


def global_xml(mats: Sequence[dict[str, str]] = ()) -> str:
    """The Global UI (status bar, buttons, per-seat prompts and playmat pickers)."""
    xml = (resources.files("lsv_duel_draft") / "lua" / "ui.xml").read_text(encoding="utf-8")
    return xml.replace("<!--MAT_PICKERS-->", mat_pickers(mats))


def ui_assets(mats: Sequence[dict[str, str]]) -> list[dict[str, Any]]:
    """Playmat thumbnails as custom UI images (``matthumb<i>``) for the pickers."""
    return [{"Type": 0, "Name": f"matthumb{i}", "URL": m["thumb"]} for i, m in enumerate(mats, 1) if m.get("thumb")]


def build_save(cards: list[Card], sheets: dict[int, Sheet], back_url: str, cube_name: str,
               basics: list[Card] | None = None, tokens: list[Token] | None = None,
               makers: dict[str, list[str]] | None = None,
               mats: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """The complete save: table, zones, cube deck, scripts and UI.

    Basic lands share the front sheets, placed after the cube's cards. Tokens
    have their own sheets; ``makers`` maps cube card id -> token labels it makes.
    ``mats`` lists the playmats players can choose (``name``, image ``url`` and ``thumb``).
    """
    basics = basics or []
    fronts, backs = assign_slots(cards + basics)
    if fronts and fronts[-1].sheet_id >= TOKEN_SHEET_BASE:
        raise ValueError("too many cards: front sheets would overlap the token sheets")
    n = len(cards)
    lands = basic_land_objects(basics, fronts[n:], sheets, back_url)
    token_data = {"tokens": token_objects(tokens or [], sheets, back_url), "makers": makers or {}}
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
        "Note": f"1v1 pick-from-5 draft of {cube_name}. Sit at White and Red, then press Start Draft.",
        "Rules": "",
        "TabStates": {},
        "Hands": {"Enable": True, "DisableUnused": False, "Hiding": 0},
        "LuaScript": global_lua(lands, token_data, mats),
        "LuaScriptState": "",
        "XmlUI": global_xml(mats or []),
        "CustomUIAssets": ui_assets(mats or []),
        "ObjectStates": [*_zones(), build_cube_deck(cards, fronts[:n], backs[:n], sheets, back_url)],
    }
