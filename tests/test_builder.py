"""Builder: Scryfall parsing, sheet layout and save-file structure (no network)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from draft_duel import sheets as sh
from draft_duel.cubes import CUBES, parse_mtgo_cardlist, resolve
from draft_duel.models import Card, Cube, Face, Sheet
from draft_duel.sources import card_from_scryfall
from draft_duel.tts_save import (
    BACK_SHEET_BASE,
    assign_slots,
    build_save,
    lua_long_string,
)

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
    save = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg")

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
    save = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg", basics)

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
    from draft_duel.tokens import load_tokens

    tokens = load_tokens()
    by_label = {t.label: t for t in tokens}
    assert len(by_label) == len(tokens) >= 50, "labels are unique"
    treasure = by_label["Treasure"]
    assert treasure.text.startswith("Token Artifact") and "Ragavan, Nimble Pilferer" in treasure.makers
    assert "Minsc & Boo, Timeless Heroes" in by_label["Boo 1/1"].makers, "commas inside names survive"
    assert by_label["Day // Night"].back_url and not treasure.back_url


def test_makers_match_cube_cards_by_any_face_name() -> None:
    from draft_duel.models import Token
    from draft_duel.tokens import match_makers

    tokens = [Token("Treasure", "", "u/t", makers=("Fable // Reflection", "Ragavan")),
              Token("Clue", "", "u/c", makers=("Not In Cube",))]
    cards = [Card("f", Face("Fable", "", "u/f"), Face("Reflection", "", "u/r")), Card("r", Face("Ragavan", "", "u/g"))]
    used, makers, missing = match_makers(tokens, cards)
    assert [t.label for t in used] == ["Treasure"]
    assert makers == {"f": ["Treasure"], "r": ["Treasure"]}
    assert missing == ["Not In Cube"]


def test_tokens_reach_the_script_with_their_own_sheet() -> None:
    import json

    from draft_duel.models import Token
    from draft_duel.tts_save import TOKEN_SHEET_BASE, assign_token_slots

    cards = [Card("a", Face("Ragavan", "", "u/a"))]
    tokens = [Token("Treasure", "Token Artifact", "u/t"), Token("Day // Night", "Card", "u/d", "u/n")]
    slots = assign_token_slots(tokens)
    assert [s.card_id for s, _ in slots] == [TOKEN_SHEET_BASE * 100, TOKEN_SHEET_BASE * 100 + 1]
    assert slots[0][1] is None and slots[1][1] is not None and slots[1][1].index == 2, "backs follow the fronts"

    fronts, _ = assign_slots(cards)
    ids = {s.sheet_id for s in fronts} | {TOKEN_SHEET_BASE}
    sheets = {i: Sheet(i, f"s{i}.jpg", f"https://h/s{i}.jpg") for i in ids}
    save = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg", tokens=tokens, makers={"a": ["Treasure"]})
    line = save["LuaScript"].split("\n")[1]
    data = json.loads(line.removeprefix("TOKENS_JSON = [==[").removesuffix("]==]"))
    assert data["makers"] == {"a": ["Treasure"]}
    treasure = data["tokens"]["Treasure"]
    assert treasure["Nickname"] == "Treasure" and json.loads(treasure["GMNotes"]) == {"token": "Treasure"}
    assert list(treasure["CustomDeck"]) == [str(TOKEN_SHEET_BASE)]
    assert "States" in data["tokens"]["Day // Night"], "double-faced tokens can be flipped"


def test_swap_cards_replaces_by_name_in_place() -> None:
    from draft_duel.sources import swap_cards

    cards = [Card("a", Face("Bolt", "", "u/a")), Card("c", Face("Cogwork Librarian", "", "u/c"))]
    tutor = Card("t", Face("Booster Tutor", "", "u/t"))
    swapped, absent = swap_cards(cards, {"Cogwork Librarian": tutor, "Not Here": tutor})
    assert [c.front.name for c in swapped] == ["Bolt", "Booster Tutor"]
    assert absent == ["Not Here"]


# ------------------------------------------------------------------ playmats


def test_playmats_render_distinct_images_of_the_mat_shape(tmp_path: Path) -> None:
    from draft_duel import playmats

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


def test_playmats_show_the_zone_board_where_it_lies(tmp_path: Path) -> None:
    # Seen in TTS: a mat covered the Library / Graveyard / Exile column painted on the table under it.
    import re

    import pytest

    from draft_duel import playmats, zones

    lua = (Path(__file__).parents[1] / "src/draft_duel/lua/table.lua").read_text()
    assert float(re.search(r"^MAT_D = ([\d.]+)", lua, re.M).group(1)) == playmats.MAT_UNITS[1]
    assert float(re.search(r"^MAT_Z = ([\d.]+)", lua, re.M).group(1)) == playmats.MAT_MID
    assert playmats.MAT_UNITS[0] / playmats.MAT_UNITS[1] == pytest.approx(playmats.W / playmats.H, rel=0.01)

    plain = Image.new("RGB", playmats.MAT_SIZE, (200, 0, 0))
    mat = playmats.with_zones(plain)
    px = playmats.W / playmats.MAT_UNITS[0]
    b = zones.BOARD

    def at(u: float, d: float) -> tuple[int, int]:
        return round((u + playmats.MAT_UNITS[0] / 2) * px), round((d - playmats.MAT_MID + playmats.MAT_UNITS[1] / 2) * px)

    for slot in zones.SLOTS.values():  # each slot's centre is painted (not the red art)
        assert mat.getpixel(at(b["u"], slot["d"])) != (200, 0, 0)
    assert mat.getpixel(at(b["u"] - b["w"] / 2 - 0.3, b["d"])) == (200, 0, 0), "the art left of the board is kept"
    assert mat.getpixel(at(0, 9.5)) == (200, 0, 0)

    written = playmats.render_all(tmp_path)
    with Image.open(tmp_path / written[0][1]) as img, Image.open(tmp_path / written[0][2]) as thumb:
        board_px = img.convert("RGB").getpixel(at(b["u"], zones.SLOTS["exile"]["d"]))
        assert board_px == pytest.approx(mat.getpixel(at(b["u"], zones.SLOTS["exile"]["d"])), abs=12), "saved mats carry it"
        assert thumb.size == playmats.THUMB_SIZE


def test_playmats_reach_the_script_and_the_dropdowns() -> None:
    import json

    cards = [Card("a", Face("Bolt", "", "u/a"))]
    fronts, _ = assign_slots(cards)
    sheets = {s.sheet_id: Sheet(s.sheet_id, "s.jpg", "https://h/s.jpg") for s in fronts}
    mats = [{"name": "Volcano", "url": "https://h/v.jpg", "thumb": "https://h/vt.jpg"},
            {"name": "Dragon's Hoard", "url": "https://h/d.jpg", "thumb": "https://h/dt.jpg"}]
    save = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg", mats=mats)
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


def test_pictures_in_the_playmats_folder_become_mats(tmp_path: Path) -> None:
    from draft_duel import playmats

    folder = tmp_path / "playmats"
    folder.mkdir()
    picture = Image.new("RGB", (1600, 900), (180, 25, 26))  # a 16:9 red wallpaper...
    picture.paste((0, 0, 0), (600, 300, 1000, 900))         # ...with a black figure
    picture.save(folder / "Black_Clover.png")
    (folder / "notes.txt").write_text("not a picture")

    assert playmats.custom_mats(folder) == [("Black Clover", folder / "Black_Clover.png")]
    mat = playmats.fit_image(folder / "Black_Clover.png")
    assert mat.size == playmats.MAT_SIZE
    r, g, b = mat.getpixel((5, 5))
    assert abs(r - 180) < 6 and g < 40 and b < 40, "the sides are filled with the picture's edge colour"
    assert mat.getpixel((playmats.W // 2, playmats.H - 5)) == (0, 0, 0), "the whole picture is shown, centred"

    written = playmats.render_all(tmp_path / "out", folder)
    assert [n for n, _, _ in written][-1] == "Black Clover" and len(written) == len(playmats.THEMES) + 1


# ------------------------------------------------------------------ cubes

MTGO_PAGE = """<html><body>
<h1 class="accordion">Starting October 7 - Vintage Cube Full Card List</h1>
<table><tr><td><strong>Color</strong></td><td><strong>Card</strong></td></tr>
{current}</table>
<h1 class="accordion">Changelist October 7</h1>
<table><tr><td>Color</td><td>In</td><td>Color</td><td>Out</td></tr>
<tr><td>White</td><td>Balance</td><td>White</td><td>Wrath of God</td></tr></table>
<h1 class="accordion">Through October 6 - Vintage Cube Full Card List</h1>
<table><tr><td>Color</td><td>Card</td></tr><tr><td>White</td><td>Wrath of God</td></tr></table>
</body></html>"""


def test_mtgo_page_gives_the_latest_full_list() -> None:
    rows = "".join(f"<tr><td>Blue</td><td>Card {i}</td></tr>" for i in range(150))
    rows += "<tr><td>Black</td><td>Bitterblossom &amp; Friends</td></tr><tr><td>Gold</td><td>Life // Death</td></tr>"
    names = parse_mtgo_cardlist(MTGO_PAGE.format(current=rows))
    assert len(names) == 152 and names[0] == "Card 0"
    assert names[-2:] == ["Bitterblossom & Friends", "Life // Death"], "entities decoded, split names kept"
    assert "Wrath of God" not in names, "the previous iteration's list is ignored"


def test_mtgo_page_without_a_full_list_is_an_error() -> None:
    import pytest

    with pytest.raises(ValueError):
        parse_mtgo_cardlist("<html>maintenance</html>")
    with pytest.raises(ValueError, match="truncated"):
        parse_mtgo_cardlist(MTGO_PAGE.format(current="<tr><td>Blue</td><td>Ancestral Recall</td></tr>"))


def test_cubes_resolve_by_key_or_cubecobra_id() -> None:
    import pytest

    assert resolve("lsv") == CUBES["lsv"] and resolve("vintage").kind == "mtgo"
    custom = resolve("cubecobra:My Pauper Cube")
    assert (custom.key, custom.kind, custom.ref) == ("my-pauper-cube", "cubecobra", "My Pauper Cube")
    with pytest.raises(ValueError):
        resolve("legacy")


def test_lua_long_string_never_ends_early() -> None:
    assert lua_long_string("abc") == "[==[abc]==]"
    assert lua_long_string("x]==]y") == "[===[x]==]y]===]"


def test_save_offers_every_cube_with_the_first_on_the_table() -> None:
    import json
    import re

    lsv, vintage = _cards(70), _cards(80, dfc_every=8)
    fronts, backs = assign_slots(lsv + vintage)
    ids = {s.sheet_id for s in fronts} | {b.sheet_id for b in backs if b}
    sheets = {i: Sheet(i, f"s{i}.jpg", f"https://h/s{i}.jpg") for i in ids}
    save = build_save([Cube("lsv", "LSV Cube", lsv), Cube("vintage", "MTGO Vintage Cube", vintage)],
                      sheets, "https://h/back.jpg")

    (table_deck,) = [o for o in save["ObjectStates"] if o["Name"] == "Deck"]
    assert table_deck["GUID"] == "c00001" and table_deck["Nickname"] == "LSV Cube"
    assert len(table_deck["ContainedObjects"]) == 70

    script = save["LuaScript"]
    cubes = json.loads(re.search(r"^CUBES_JSON = \[==\[(.*)\]==\]$", script, re.MULTILINE).group(1))
    assert cubes == [{"key": "lsv", "name": "LSV Cube", "count": 70},
                     {"key": "vintage", "name": "MTGO Vintage Cube", "count": 80}]
    decks = dict(re.findall(r'\["(\w+)"\] = \[==\[(.*?)\]==\]', script.split("CUBE_DECKS = ", 1)[1].split("\n", 1)[0]))
    vintage_deck = json.loads(decks["vintage"])
    assert json.loads(decks["lsv"]) == table_deck
    assert vintage_deck["Nickname"] == "MTGO Vintage Cube" and len(vintage_deck["ContainedObjects"]) == 80

    guids = [c["GUID"] for d in (table_deck, vintage_deck) for c in d["ContainedObjects"]]
    assert len(guids) == len(set(guids)), "card GUIDs are unique across cubes"
    lsv_sheets = {s.sheet_id for s in fronts[:70]}
    assert {int(k) for k in table_deck["CustomDeck"]} == lsv_sheets, "a deck only loads its own sheets"
    assert 'id="cubePick_White_2"' in save["XmlUI"] and 'id="cubeButton_Red"' in save["XmlUI"]
    assert "LSV Cube, MTGO Vintage Cube" in save["Note"]


def test_a_single_cube_save_has_no_picker() -> None:
    cards = _cards(10)
    fronts, _ = assign_slots(cards)
    sheets = {s.sheet_id: Sheet(s.sheet_id, "s.jpg", "https://h/s.jpg") for s in fronts}
    save = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg")
    assert "cubePick_" not in save["XmlUI"]


# ------------------------------------------------------------------ zone board


def test_zone_board_image_matches_its_layout_and_reaches_the_script(tmp_path: Path) -> None:
    import json

    from draft_duel import zones

    name = zones.render_all(tmp_path)
    assert zones.render_all(tmp_path) == name, "drawing is deterministic"
    with Image.open(tmp_path / name) as img:
        w, h = img.size
    assert abs(w / h - zones.BOARD["w"] / zones.BOARD["h"]) < 0.01, "a tile's width follows the image"
    top, bottom = zones.BOARD["d"] - zones.BOARD["h"] / 2, zones.BOARD["d"] + zones.BOARD["h"] / 2
    for area in (*zones.SLOTS.values(), *zones.BUTTONS.values()):
        assert top < area["d"] - area["h"] / 2 and area["d"] + area["h"] / 2 < bottom, "inside the board"
    assert zones.BOARD["u"] + zones.BOARD["w"] / 2 <= 22, "inside the 44-wide playmat"

    cards = [Card("a", Face("Bolt", "", "u/a"))]
    fronts, _ = assign_slots(cards)
    sheets = {s.sheet_id: Sheet(s.sheet_id, "s.jpg", "https://h/s.jpg") for s in fronts}
    save = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg", zones_url="https://h/z.jpg")
    line = next(x for x in save["LuaScript"].splitlines() if x.startswith("ZONES_JSON = "))
    data = json.loads(line.removeprefix("ZONES_JSON = [==[").removesuffix("]==]"))
    assert data["url"] == "https://h/z.jpg" and data["slots"] == zones.SLOTS
    plain = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg")
    assert "ZONES_JSON = [==[{}]==]" in plain["LuaScript"], "no image, no board"


# ------------------------------------------------------------------ table top


def test_table_image_fits_the_custom_table_and_reaches_the_save(tmp_path: Path) -> None:
    from draft_duel import tabletop, zones

    name = tabletop.render_all(tmp_path)
    assert tabletop.render_all(tmp_path) == name, "drawing is deterministic"
    with Image.open(tmp_path / name) as img:
        w, h = img.size
    assert max(w, h) <= 4096
    assert abs(w / h - tabletop.TABLE_W / tabletop.TABLE_H) < 0.005, "TTS stretches the image over the table"
    assert tabletop.PANEL_W >= 44, "the painted mat is at least as wide as the in-game playmat"
    assert zones.BOARD["u"] + zones.BOARD["w"] / 2 < tabletop.PANEL_W / 2, "the zone slots are on the painted mat"
    assert tabletop.MAT_MID + tabletop.MAT_D / 2 + tabletop.FRAME < tabletop.TABLE_H / 2

    cards = [Card("a", Face("Bolt", "", "u/a"))]
    fronts, _ = assign_slots(cards)
    sheets = {s.sheet_id: Sheet(s.sheet_id, "s.jpg", "https://h/s.jpg") for s in fronts}
    save = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg", table_url="https://h/t.jpg")
    assert save["Table"] == "Table_Custom" and save["TableURL"] == "https://h/t.jpg"
    plain = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg")
    assert plain["Table"] == "Table_RPG" and "TableURL" not in plain


# ------------------------------------------------------------------ table props


def test_props_are_read_from_the_edh_save_locked_and_never_collide(tmp_path: Path) -> None:
    import json

    from draft_duel import props

    wanted = [g for guids in props.PROP_GUIDS.values() for g in guids]
    objs = [{"GUID": g, "Name": "Infinite_Bag", "Locked": False,
             "ContainedObjects": [{"GUID": "c00001", "Name": "Die_20"}]} for g in wanted]
    objs.append({"GUID": "ffffff", "Name": "Custom_Token", "Nickname": "Card Importer"})  # not a prop
    save_file = tmp_path / f"{props.WORKSHOP_ID}.json"
    save_file.write_text(json.dumps({"ObjectStates": objs}), encoding="utf-8")

    loaded = props.load_props(save_file)
    assert [o["GUID"] for o in loaded] == wanted and all(o["Locked"] for o in loaded)
    assert props.load_props(None) == [] and props.load_props(tmp_path / "missing.json") == []

    cards = [Card("a", Face("Bolt", "", "u/a"))]
    fronts, _ = assign_slots(cards)
    sheets = {s.sheet_id: Sheet(s.sheet_id, "s.jpg", "https://h/s.jpg") for s in fronts}
    save = build_save([Cube("lsv", "LSV Cube", cards)], sheets, "https://h/back.jpg", props=loaded)

    def guids(o):
        return [o["GUID"]] + [g for c in o.get("ContainedObjects") or [] for g in guids(c)]
    every = [g for o in save["ObjectStates"] for g in guids(o)]
    assert len(every) == len(set(every)), "no GUID is used twice"
    assert save["ObjectStates"][2]["GUID"] == "c00001", "the cube keeps its fixed GUID"
    assert len(save["ObjectStates"]) == 3 + len(wanted)


def test_props_name_what_the_edh_mod_no_longer_has(tmp_path: Path) -> None:
    import json

    import pytest

    from draft_duel import props

    save_file = tmp_path / "edh.json"
    save_file.write_text(json.dumps({"ObjectStates": []}), encoding="utf-8")
    with pytest.raises(KeyError, match="no longer has props"):
        props.load_props(save_file)


def test_prop_cards_move_from_dead_scryfall_hosts_onto_our_sheets() -> None:
    from draft_duel import props

    def card(guid: str, url: str, card_id: int) -> dict:
        return {"GUID": guid, "Name": "Card", "CardID": card_id,
                "CustomDeck": {str(card_id // 100): {"FaceURL": url, "BackURL": "https://dead/back.jpg",
                                                     "NumWidth": 1, "NumHeight": 1}}}
    old = "https://c1.scryfall.com/file/scryfall-cards/normal/front/5/8/aaa.jpg"
    deck = {"GUID": "d40d7e", "Name": "Deck", "DeckIDs": [5500, 5400],
            "CustomDeck": {}, "ContainedObjects": [card("x1", old, 5500),
                                                   card("x2", "https://cards.scryfall.io/large/back/2/c/bbb.jpg?1", 5400)]}
    bag = {"GUID": "a87f74", "Name": "Custom_Model_Bag", "ContainedObjects": [card("x3", old, 100)]}
    steam = {"GUID": "b1", "Name": "Card", "CardID": 200,
             "CustomDeck": {"2": {"FaceURL": "https://steamusercontent-a.akamaihd.net/ugc/1/", "BackURL": "b"}}}

    faces = props.card_faces([deck, bag, steam])
    assert faces == ["https://cards.scryfall.io/normal/front/5/8/aaa.jpg",
                     "https://cards.scryfall.io/large/back/2/c/bbb.jpg?1"], "deduplicated, current host, Steam untouched"
    base = props.PROP_SHEET_BASE
    entry = {base: {"FaceURL": "https://h/props01.jpg", "BackURL": "https://h/back.jpg", "NumWidth": 10, "NumHeight": 7}}
    new_deck, new_bag, new_steam = props.rehost([deck, bag, steam], faces, entry, per_sheet=69)
    assert [c["CardID"] for c in new_deck["ContainedObjects"]] == [base * 100, base * 100 + 1]
    assert new_deck["DeckIDs"] == [base * 100, base * 100 + 1] and set(new_deck["CustomDeck"]) == {str(base)}
    assert new_bag["ContainedObjects"][0]["CardID"] == base * 100, "the same image shares a slot"
    assert new_steam == steam and deck["DeckIDs"] == [5500, 5400], "originals are left alone"


def test_custom_tokens_and_double_faced_prop_cards_are_rehosted_too() -> None:
    from draft_duel import props

    old_png = "https://c1.scryfall.com/file/scryfall-cards/png/front/4/7/poison.png?1"
    bag = {"GUID": "81ae86", "Name": "Custom_Model_Infinite_Bag",
           "ContainedObjects": [{"GUID": "t1", "Name": "Custom_Token", "CustomImage": {"ImageURL": old_png}}]}
    label = {"GUID": "b86992", "Name": "Custom_Token", "CustomImage": {"ImageURL": old_png}}
    day = {"GUID": "c1", "Name": "Card", "CardID": 100,
           "CustomDeck": {"1": {"FaceURL": "https://c1.scryfall.com/file/scryfall-cards/normal/front/9/c/day.jpg"}},
           "States": {"2": {"GUID": "c2", "Name": "Card", "CardID": 200, "CustomDeck": {
               "2": {"FaceURL": "https://c1.scryfall.com/file/scryfall-cards/normal/back/9/c/day.jpg"}}}}}

    assert props.token_images([bag, label]) == ["https://cards.scryfall.io/png/front/4/7/poison.png?1"]
    new_bag, new_label = props.rehost_tokens([bag, label], {props.token_images([bag])[0]: "https://h/poison.png"})
    assert new_bag["ContainedObjects"][0]["CustomImage"]["ImageURL"] == "https://h/poison.png"
    assert new_label["CustomImage"]["ImageURL"] == "https://h/poison.png"

    faces = props.card_faces([day])
    assert len(faces) == 2, "the Night face is a card state and is rehosted too"
    (new_day,) = props.rehost([day], faces, {props.PROP_SHEET_BASE: {"FaceURL": "https://h/p.jpg"}}, per_sheet=69)
    assert new_day["States"]["2"]["CardID"] == props.PROP_SHEET_BASE * 100 + 1


def test_build_names_sheets_the_branch_lacks(tmp_path: Path, monkeypatch) -> None:
    import subprocess

    from draft_duel import cli

    for name in ("front01-aaa.jpg", "front09-new.jpg", "proptoken01-bbb.png"):
        (tmp_path / name).write_bytes(b"x")
    calls: list[tuple[str, ...]] = []

    def fake_git(*args: str) -> str:
        calls.append(args)
        return "sheets/front01-aaa.jpg\nsheets/front09-old.jpg\nsheets/proptoken01-bbb.png"

    monkeypatch.setattr(cli, "_git", fake_git)
    assert cli.unpublished_sheets("main", tmp_path) == ["front09-new.jpg"]
    assert calls == [("ls-tree", "--name-only", "origin/main", "sheets/")]

    def no_branch(*args: str) -> str:
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(cli, "_git", no_branch)
    assert len(cli.unpublished_sheets("gone", tmp_path)) == 3, "an unknown branch has none of them"
