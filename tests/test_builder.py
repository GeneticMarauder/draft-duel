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

    names = [(o["Name"], o.get("FogColor")) for o in save["ObjectStates"] if o["Name"] != "Deck"]
    assert names == [("HandTrigger", "White"), ("HandTrigger", "Red")], "no hidden-zone blocks on the table"
    assert "DraftCore" in save["LuaScript"] and "onStartClicked" in save["XmlUI"]


def test_cards_carry_deck_editor_data_and_basics_reach_the_script() -> None:
    import json

    cards = [Card("a", Face("Bolt", "", "u/a"), cmc=1, is_land=False),
             Card("b", Face("Wasteland", "", "u/b"), cmc=0, is_land=True)]
    basics = [Card("p", Face("Plains", "", "u/p"), is_land=True)]
    fronts, _ = assign_slots(cards + basics)
    sheets = {s.sheet_id: Sheet(s.sheet_id, "s.jpg", "https://h/s.jpg") for s in fronts}
    save = build_save(cards, sheets, "https://h/back.jpg", "LSVCube", basics)

    deck = next(o for o in save["ObjectStates"] if o["Name"] == "Deck")
    notes = [json.loads(c["GMNotes"]) for c in deck["ContainedObjects"]]
    assert notes == [{"id": "a", "cmc": 1, "land": False, "basic": False},
                     {"id": "b", "cmc": 0, "land": True, "basic": False}]
    header = save["LuaScript"].split("\n", 1)[0]
    lands = json.loads(header.removeprefix("BASIC_LANDS_JSON = [==[").removesuffix("]==]"))
    assert [b["Nickname"] for b in lands] == ["Plains"]
    assert json.loads(lands[0]["GMNotes"])["basic"] is True
    assert lands[0]["CardID"] == fronts[2].card_id, "basics sit on the sheets after the cube's cards"


# ------------------------------------------------------------------ tokens


def test_bundled_token_list_parses() -> None:
    from lsv_duel_draft.tokens import load_tokens

    tokens = load_tokens()
    by_label = {t.label: t for t in tokens}
    assert len(by_label) == len(tokens) >= 50, "labels are unique"
    treasure = by_label["Treasure"]
    assert treasure.text.startswith("Token Artifact") and "Ragavan, Nimble Pilferer" in treasure.makers
    assert "Minsc & Boo, Timeless Heroes" in by_label["Boo 1/1"].makers, "commas inside names survive"
    assert by_label["Day // Night"].back_url and not treasure.back_url


def test_makers_match_cube_cards_by_any_face_name() -> None:
    from lsv_duel_draft.models import Token
    from lsv_duel_draft.tokens import match_makers

    tokens = [Token("Treasure", "", "u/t", makers=("Fable // Reflection", "Ragavan")),
              Token("Clue", "", "u/c", makers=("Not In Cube",))]
    cards = [Card("f", Face("Fable", "", "u/f"), Face("Reflection", "", "u/r")), Card("r", Face("Ragavan", "", "u/g"))]
    used, makers, missing = match_makers(tokens, cards)
    assert [t.label for t in used] == ["Treasure"]
    assert makers == {"f": ["Treasure"], "r": ["Treasure"]}
    assert missing == ["Not In Cube"]


def test_tokens_reach_the_script_with_their_own_sheet() -> None:
    import json

    from lsv_duel_draft.models import Token
    from lsv_duel_draft.tts_save import TOKEN_SHEET_BASE, assign_token_slots

    cards = [Card("a", Face("Ragavan", "", "u/a"))]
    tokens = [Token("Treasure", "Token Artifact", "u/t"), Token("Day // Night", "Card", "u/d", "u/n")]
    slots = assign_token_slots(tokens)
    assert [s.card_id for s, _ in slots] == [TOKEN_SHEET_BASE * 100, TOKEN_SHEET_BASE * 100 + 1]
    assert slots[0][1] is None and slots[1][1] is not None and slots[1][1].index == 2, "backs follow the fronts"

    fronts, _ = assign_slots(cards)
    ids = {s.sheet_id for s in fronts} | {TOKEN_SHEET_BASE}
    sheets = {i: Sheet(i, f"s{i}.jpg", f"https://h/s{i}.jpg") for i in ids}
    save = build_save(cards, sheets, "https://h/back.jpg", "LSVCube", tokens=tokens, makers={"a": ["Treasure"]})
    line = save["LuaScript"].split("\n")[1]
    data = json.loads(line.removeprefix("TOKENS_JSON = [==[").removesuffix("]==]"))
    assert data["makers"] == {"a": ["Treasure"]}
    treasure = data["tokens"]["Treasure"]
    assert treasure["Nickname"] == "Treasure" and json.loads(treasure["GMNotes"]) == {"token": "Treasure"}
    assert list(treasure["CustomDeck"]) == [str(TOKEN_SHEET_BASE)]
    assert "States" in data["tokens"]["Day // Night"], "double-faced tokens can be flipped"


def test_swap_cards_replaces_by_name_in_place() -> None:
    from lsv_duel_draft.sources import swap_cards

    cards = [Card("a", Face("Bolt", "", "u/a")), Card("c", Face("Cogwork Librarian", "", "u/c"))]
    tutor = Card("t", Face("Booster Tutor", "", "u/t"))
    swapped, absent = swap_cards(cards, {"Cogwork Librarian": tutor, "Not Here": tutor})
    assert [c.front.name for c in swapped] == ["Bolt", "Booster Tutor"]
    assert absent == ["Not Here"]


# ------------------------------------------------------------------ playmats


def test_playmats_render_distinct_images_of_the_mat_shape(tmp_path: Path) -> None:
    from lsv_duel_draft import playmats

    written = playmats.render_all(tmp_path)
    assert len(written) == len(playmats.THEMES) >= 10
    names = [n for n, _, _ in written]
    files = [f for _, f, _ in written]
    assert len(set(files)) == len(files), "every mat looks different (content-hashed names)"
    with Image.open(tmp_path / files[0]) as img:
        assert img.size == playmats.MAT_SIZE
    with Image.open(tmp_path / written[0][2]) as thumb:
        assert thumb.size == playmats.THUMB_SIZE
    assert playmats.render_all(tmp_path) == written, "drawing is deterministic"
    assert all(n.isprintable() and not any(c in n for c in '<>&"') for n in names)


def test_playmats_reach_the_script_and_the_dropdowns() -> None:
    import json

    cards = [Card("a", Face("Bolt", "", "u/a"))]
    fronts, _ = assign_slots(cards)
    sheets = {s.sheet_id: Sheet(s.sheet_id, "s.jpg", "https://h/s.jpg") for s in fronts}
    mats = [{"name": "Volcano", "url": "https://h/v.jpg", "thumb": "https://h/vt.jpg"},
            {"name": "Dragon's Hoard", "url": "https://h/d.jpg", "thumb": "https://h/dt.jpg"}]
    save = build_save(cards, sheets, "https://h/back.jpg", "LSVCube", mats=mats)
    line = save["LuaScript"].splitlines()[2]
    assert json.loads(line.removeprefix("MATS_JSON = [==[").removesuffix("]==]")) == mats
    xml = save["XmlUI"]
    assert "<!--MAT_PICKERS-->" not in xml
    for color in ("White", "Red"):
        assert f'id="matPicker_{color}" visibility="{color}"' in xml and f'id="matPick_{color}_0"' in xml
        assert f'id="matPick_{color}_2" onClick="onMatPick" image="matthumb2"' in xml
    assert xml.count(">Dragon's Hoard</Text>") == 2, "one picker per seat"
    assert save["CustomUIAssets"] == [{"Type": 0, "Name": "matthumb1", "URL": "https://h/vt.jpg"},
                                      {"Type": 0, "Name": "matthumb2", "URL": "https://h/dt.jpg"}]
    import xml.etree.ElementTree as ET
    ET.fromstring(f"<root>{xml}</root>")  # well-formed
