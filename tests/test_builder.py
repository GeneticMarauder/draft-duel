"""Builder: Scryfall parsing, sheet layout and save-file structure (no network)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from lsv_duel_draft import sheets as sh
from lsv_duel_draft.models import Card, Face, Sheet
from lsv_duel_draft.sources import card_from_scryfall
from lsv_duel_draft.tts_save import BACK_SHEET_BASE, assign_slots, build_save

NORMAL = {"id": "n1", "name": "Lightning Bolt", "type_line": "Instant", "mana_cost": "{R}",
          "oracle_text": "Deal 3.", "image_uris": {"normal": "https://x/normal/front/a/b/n1.jpg"}}
DFC = {"id": "d1", "name": "Delver // Aberration", "card_faces": [
    {"name": "Delver", "type_line": "Creature", "mana_cost": "{U}", "oracle_text": "Flip.",
     "power": "1", "toughness": "1", "image_uris": {"normal": "https://x/normal/front/c/d/d1.jpg"}},
    {"name": "Aberration", "type_line": "Creature", "mana_cost": "", "oracle_text": "Flying",
     "power": "3", "toughness": "2", "image_uris": {"normal": "https://x/normal/back/c/d/d1.jpg"}}]}
SPLIT = {"id": "s1", "name": "Fire // Ice", "image_uris": {"normal": "https://x/normal/front/e/f/s1.jpg"},
         "card_faces": [{"name": "Fire", "type_line": "Instant", "mana_cost": "{1}{R}", "oracle_text": "2 dmg."},
                        {"name": "Ice", "type_line": "Instant", "mana_cost": "{1}{U}", "oracle_text": "Tap."}]}


def test_parses_normal_dfc_and_split_cards() -> None:
    bolt = card_from_scryfall(NORMAL)
    assert bolt.back is None and "Deal 3." in bolt.front.text

    delver = card_from_scryfall(DFC)
    assert delver.front.name == "Delver" and delver.back is not None
    assert delver.back.image_url.endswith("/back/c/d/d1.jpg")
    assert "[b]3/2[/b]" in delver.back.text

    fire_ice = card_from_scryfall(SPLIT)
    assert fire_ice.back is None
    assert "Fire" in fire_ice.front.text and "Ice" in fire_ice.front.text


def _cards(n: int, dfc_every: int = 0) -> list[Card]:
    out = []
    for i in range(n):
        back = Face(f"B{i}", "", f"u/back/{i}") if dfc_every and i % dfc_every == 0 else None
        out.append(Card(f"id{i}", Face(f"C{i}", "", f"u/front/{i}"), back))
    return out


def test_slots_fill_sheets_in_order() -> None:
    fronts, backs = assign_slots(_cards(200, dfc_every=10))
    assert fronts[0].card_id == 100 and fronts[68].card_id == 168
    assert fronts[69].card_id == 200  # sheet 2 starts after 69 cards
    assert backs[0] is not None and backs[0].sheet_id == BACK_SHEET_BASE
    assert backs[1] is None
    assert len({f.card_id for f in fronts}) == 200


def test_render_sheet_size(tmp_path: Path) -> None:
    img_path = tmp_path / "c.jpg"
    Image.new("RGB", (488, 680), "red").save(img_path)
    sheet = sh.render_sheet([img_path] * 3)
    assert sheet.size == (sh.CARD_W * 10, sh.CARD_H * 7)
    assert max(sheet.size) <= 4096


def test_save_structure() -> None:
    cards = _cards(140, dfc_every=7)
    fronts, backs = assign_slots(cards)
    ids = {s.sheet_id for s in fronts} | {b.sheet_id for b in backs if b}
    sheets = {i: Sheet(i, f"s{i}.jpg", f"https://h/s{i}.jpg") for i in ids}
    save = build_save(cards, sheets, "https://h/back.jpg", "LSVCube")

    deck = next(o for o in save["ObjectStates"] if o["Name"] == "Deck")
    assert deck["GUID"] == "c00001" and len(deck["ContainedObjects"]) == 140
    assert deck["DeckIDs"] == [c["CardID"] for c in deck["ContainedObjects"]]
    guids = [c["GUID"] for c in deck["ContainedObjects"]]
    guids += [c["States"]["2"]["GUID"] for c in deck["ContainedObjects"] if "States" in c]
    assert len(guids) == len(set(guids))
    assert sum(1 for c in deck["ContainedObjects"] if "States" in c) == 20
    assert all(int(k) < BACK_SHEET_BASE for k in deck["CustomDeck"])

    zones = {(o["Name"], o["FogColor"]) for o in save["ObjectStates"] if "FogColor" in o}
    assert zones == {("HandTrigger", "White"), ("HandTrigger", "Red"),
                     ("FogOfWarTrigger", "White"), ("FogOfWarTrigger", "Red")}
    assert "DraftCore" in save["LuaScript"] and "onStartClicked" in save["XmlUI"]
