"""Assemble the Tabletop Simulator save file (JSON) for the duel draft table."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from importlib import resources
from typing import Any

from draft_duel import zones
from draft_duel.props import merge as merge_props
from draft_duel.models import Card, Cube, Sheet, SheetSlot, Token
from draft_duel.sheets import COLS, PER_SHEET, ROWS
from draft_duel.tokens import token_faces

SAVE_NAME = "Draft Duel"
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


CUBE_Y = 2.01  # the cube deck's centre resting on Table_RPG's felt (seen in TTS); lower starts it inside the table


def _transform(x: float = 0, y: float = 1, z: float = 0, ry: float = 0, rz: float = 0,
               sx: float = 1, sy: float = 1, sz: float = 1) -> dict[str, float]:
    return {"posX": x, "posY": y, "posZ": z, "rotX": 0, "rotY": ry, "rotZ": rz,
            "scaleX": sx, "scaleY": sy, "scaleZ": sz}


def deck_entry(sheet: Sheet, back_url: str) -> dict[str, Any]:
    """A ``CustomDeck`` entry for one of our sheets."""
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
        "CustomDeck": {str(slot.sheet_id): deck_entry(sheets[slot.sheet_id], back_url)},
        "HideWhenFaceDown": True,
        "Hands": True,
        "Tooltip": True,
        "Sticky": False,  # picking a card up never drags the cards resting on it
    }


def build_cube_deck(cards: list[Card], fronts: Sequence[SheetSlot], backs: Sequence[SheetSlot | None],
                    sheets: dict[int, Sheet], back_url: str, name: str = "Cube",
                    first_index: int = 0) -> dict[str, Any]:
    """The face-down cube deck; double-faced cards carry their back as state 2.

    ``first_index`` offsets the card GUIDs so several cubes in one save never share one.
    """
    contained = []
    for i, (card, front, back) in enumerate(zip(cards, fronts, backs, strict=True), first_index):
        note = card_note(card)
        obj = _card_object(f"{0xd00000 + i:06x}", card.front.name, card.front.text, note, front, sheets, back_url)
        if card.back is not None and back is not None:
            obj["States"] = {"2": _card_object(f"{0xe00000 + i:06x}", card.back.name, card.back.text,
                                               note, back, sheets, back_url)}
        contained.append(obj)
    return {
        "GUID": CUBE_GUID,
        "Name": "Deck",
        "Transform": _transform(x=-6, y=CUBE_Y, ry=180, rz=180),
        "Nickname": name,
        "Description": f"{len(cards)} cards",
        "DeckIDs": [s.card_id for s in fronts],
        # Only this cube's sheets, so TTS doesn't fetch the other cubes' images.
        "CustomDeck": {str(i): deck_entry(sheets[i], back_url) for i in sorted({s.sheet_id for s in fronts})},
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


def lua_long_string(text: str) -> str:
    """``text`` as a Lua long string (``[==[...]==]``), with enough ``=`` that the text can't end it."""
    level = 2
    while f"]{'=' * level}]" in text:
        level += 1
    eq = "=" * level
    return f"[{eq}[{text}]{eq}]"


def global_lua(basic_lands: list[dict[str, Any]] | None = None,
               tokens: dict[str, Any] | None = None,
               mats: list[dict[str, str]] | None = None,
               cubes: list[dict[str, Any]] | None = None,
               cube_decks: dict[str, dict[str, Any]] | None = None,
               zones: dict[str, Any] | None = None) -> str:
    """The Global script: data headers, rules engine, then the table adapter.

    ``tokens`` is ``{"tokens": {label: card data}, "makers": {card id: [label, ...]}}``;
    ``mats`` is ``[{"name": ..., "url": ...}, ...]``; ``cubes`` is
    ``[{"key", "name", "count"}, ...]`` and ``cube_decks`` maps each key to its
    deck's save data, which the script spawns (``spawnObjectJSON``) when players
    switch cubes. The decks stay JSON strings so loading the save decodes nothing.
    ``zones`` is the zone board (``zones.LAYOUT`` plus its image ``url``); without it
    the game has no board, only the default library spot.
    """
    pkg = resources.files("draft_duel") / "lua"
    decks = ", ".join(f"[{json.dumps(key)}] = {lua_long_string(json.dumps(deck))}"
                      for key, deck in (cube_decks or {}).items())
    header = (f"BASIC_LANDS_JSON = {lua_long_string(json.dumps(basic_lands or []))}\n"
              f"TOKENS_JSON = {lua_long_string(json.dumps(tokens or {'tokens': {}, 'makers': {}}))}\n"
              f"MATS_JSON = {lua_long_string(json.dumps(mats or []))}\n"
              f"CUBES_JSON = {lua_long_string(json.dumps(cubes or []))}\n"
              f"ZONES_JSON = {lua_long_string(json.dumps(zones or {}))}\n"
              f"CUBE_DECKS = {{ {decks} }}\n")
    return (header + (pkg / "draft_core.lua").read_text(encoding="utf-8") + "\n"
            + (pkg / "table.lua").read_text(encoding="utf-8"))


def cube_pickers(cubes: Sequence[dict[str, Any]]) -> str:
    """Per-seat cube pickers: a mid-screen list of the cubes, shown only to that seat."""
    if any(c in cube["name"] for cube in cubes for c in '<>&"'):
        raise ValueError("cube names must not need XML escaping (TTS shows entities literally)")
    if len(cubes) < 2:
        return ""
    height = 100 + len(cubes) * 66
    panels = []
    for color in ("White", "Red"):
        rows = "".join(
            f'<Button id="cubePick_{color}_{i}" onClick="onCubePick" preferredHeight="56" fontSize="20" '
            f'textColor="#FFFFFF" colors="#283593|#3949AB|#1A237E|#555555">{cube["name"]}  ({cube["count"]} cards)</Button>'
            for i, cube in enumerate(cubes, 1))
        panels.append(
            f'<Panel id="cubePicker_{color}" visibility="{color}" active="false" rectAlignment="MiddleCenter" '
            f'width="560" height="{height}" color="#101018F2">'
            '<VerticalLayout padding="16 16 12 16" spacing="10" childForceExpandHeight="false">'
            '<HorizontalLayout preferredHeight="36" spacing="10" childForceExpandWidth="false">'
            '<Text fontSize="22" color="#FFFFFF" alignment="MiddleLeft" flexibleWidth="1">Choose the cube</Text>'
            f'<Button id="cubeClose_{color}" preferredWidth="110" fontSize="16" onClick="onCubeButton" '
            'textColor="#FFFFFF" colors="#37474F|#455A64|#263238|#555555">Close</Button>'
            '</HorizontalLayout>' + rows + '</VerticalLayout></Panel>')
    return "\n".join(panels)


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
    rows = (len(mats) + 1 + 3) // 4  # four thumbnails per row, plus "None"
    height = 90 + rows * 122
    panels = []
    for color in ("White", "Red"):
        cells = [_mat_cell(color, 0, "None", None)]
        cells += [_mat_cell(color, i, m["name"], f"matthumb{i}") for i, m in enumerate(mats, 1)]
        panels.append(
            f'<Panel id="matPicker_{color}" visibility="{color}" active="false" rectAlignment="MiddleCenter" '
            f'width="1000" height="{height}" color="#101018F2">'
            '<VerticalLayout padding="16 16 12 16" spacing="10" childForceExpandHeight="false">'
            '<HorizontalLayout preferredHeight="36" spacing="10" childForceExpandWidth="false">'
            '<Text fontSize="22" color="#FFFFFF" alignment="MiddleLeft" flexibleWidth="1">Choose your playmat</Text>'
            f'<Button id="matClose_{color}" preferredWidth="110" fontSize="16" onClick="onMatButton" '
            'textColor="#FFFFFF" colors="#37474F|#455A64|#263238|#555555">Close</Button>'
            '</HorizontalLayout>'
            '<GridLayout cellSize="230 112" spacing="10 10" constraint="FixedColumnCount" constraintCount="4">'
            + "".join(cells) + '</GridLayout></VerticalLayout></Panel>')
    return "\n".join(panels)


def global_xml(mats: Sequence[dict[str, str]] = (), cubes: Sequence[dict[str, Any]] = ()) -> str:
    """The Global UI (status bar, buttons, per-seat prompts, playmat and cube pickers)."""
    xml = (resources.files("draft_duel") / "lua" / "ui.xml").read_text(encoding="utf-8")
    return xml.replace("<!--MAT_PICKERS-->", mat_pickers(mats)).replace("<!--CUBE_PICKERS-->", cube_pickers(cubes))


def ui_assets(mats: Sequence[dict[str, str]]) -> list[dict[str, Any]]:
    """Playmat thumbnails as custom UI images (``matthumb<i>``) for the pickers."""
    return [{"Type": 0, "Name": f"matthumb{i}", "URL": m["thumb"]} for i, m in enumerate(mats, 1) if m.get("thumb")]


def build_save(cubes: list[Cube], sheets: dict[int, Sheet], back_url: str,
               basics: list[Card] | None = None, tokens: list[Token] | None = None,
               makers: dict[str, list[str]] | None = None,
               mats: list[dict[str, str]] | None = None,
               zones_url: str | None = None, table_url: str | None = None,
               props: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """The complete save: table, zones, cube deck, scripts and UI.

    The first cube is on the table when the save loads; every cube's deck is also
    embedded in the script so players can switch before the draft starts. Cards
    take the front sheets cube by cube, then the basic lands. Tokens have their
    own sheets; ``makers`` maps card id -> token labels it makes. ``mats`` lists
    the playmats players can choose (``name``, image ``url`` and ``thumb``);
    ``zones_url`` is the zone board image (see ``zones.py``); ``table_url`` the
    table top (see ``tabletop.py``), on TTS's custom rectangle table (without it, ``Table_RPG``);
    ``props`` are extra objects for the table's ends (see ``props.py``).
    """
    if not cubes:
        raise ValueError("a save needs at least one cube")
    basics = basics or []
    all_cards = [c for cube in cubes for c in cube.cards]
    fronts, backs = assign_slots(all_cards + basics)
    if fronts and fronts[-1].sheet_id >= TOKEN_SHEET_BASE:
        raise ValueError("too many cards: front sheets would overlap the token sheets")
    decks: dict[str, dict[str, Any]] = {}
    start = 0
    for cube in cubes:
        end = start + len(cube.cards)
        decks[cube.key] = build_cube_deck(cube.cards, fronts[start:end], backs[start:end], sheets, back_url,
                                          cube.name, first_index=start)
        start = end
    cube_list = [{"key": c.key, "name": c.name, "count": len(c.cards)} for c in cubes]
    names = ", ".join(c.name for c in cubes)
    lands = basic_land_objects(basics, fronts[len(all_cards):], sheets, back_url)
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
        "Table": "Table_Custom" if table_url else "Table_RPG",
        **({"TableURL": table_url} if table_url else {}),
        "Sky": "Sky_Museum",
        "Note": (f"Draft Duel: a 1v1 pick-from-5 cube draft. Cubes: {names}. Choose one with the Cube button, "
                 "sit at White and Red, then press Start Draft."),
        "Rules": "",
        "TabStates": {},
        "Hands": {"Enable": True, "DisableUnused": False, "Hiding": 0},
        "LuaScript": global_lua(lands, token_data, mats, cube_list, decks,
                                 {**zones.LAYOUT, "url": zones_url} if zones_url else None),
        "LuaScriptState": "",
        "XmlUI": global_xml(mats or [], cube_list),
        "CustomUIAssets": ui_assets(mats or []),
        "ObjectStates": merge_props([*_zones(), decks[cubes[0].key]], props or []),
    }
