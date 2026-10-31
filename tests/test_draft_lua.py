"""Runs the real Lua (rules engine + table adapter) under lupa with a mocked TTS API."""

from __future__ import annotations

import itertools
import json
from importlib import resources
from pathlib import Path
from typing import Any

from lupa import LuaRuntime

from draft_duel import zones

LUA_DIR = resources.files("draft_duel") / "lua"
MOCK = Path(__file__).parent / "lua" / "tts_mock.lua"


def _to_py(value: Any) -> Any:
    if hasattr(value, "items") and type(value).__name__ == "_LuaTable":
        d = {k: _to_py(v) for k, v in value.items()}
        if d and all(isinstance(k, int) for k in d) and sorted(d) == list(range(1, len(d) + 1)):
            return [d[i] for i in range(1, len(d) + 1)]
        return d
    return value


def make_lua(with_table: bool = False) -> LuaRuntime:
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute((LUA_DIR / "draft_core.lua").read_text(encoding="utf-8"))
    if with_table:
        lua.execute(MOCK.read_text(encoding="utf-8"))
        g = lua.globals()
        g.JSON = lua.table(
            encode=lambda t: json.dumps(_to_py(t)),
            decode=lambda s: lua.table_from(json.loads(s), recursive=True),
        )
        g.BASIC_LANDS_JSON = json.dumps([
            {"Name": "Card", "Nickname": n,
             "GMNotes": json.dumps({"id": n, "cmc": 0, "land": True, "basic": True})}
            for n in ("Plains", "Island", "Swamp", "Mountain", "Forest")
        ])
        g.TOKENS_JSON = json.dumps(TOKENS)
        g.MATS_JSON = json.dumps([{"name": n, "url": f"https://h/{n}.jpg"} for n in ("Volcano", "Aurora")])
        g.ZONES_JSON = json.dumps({**zones.LAYOUT, "url": "https://h/zones.jpg"})
        g.CUBES_JSON = json.dumps([{"key": k, "name": n, "count": c} for k, n, c in CUBES])
        g.CUBE_DECKS = lua.table_from({k: json.dumps({"Name": "Deck", "Nickname": n, "ContainedObjects": [{}] * c})
                                       for k, n, c in CUBES})
        lua.execute((LUA_DIR / "table.lua").read_text(encoding="utf-8"))
    return lua


# The save's cubes: the first (515 cards, like Mock.setup(515)'s deck) is on the table at load.
CUBES = [("lsv", "LSV Cube", 515), ("vintage", "MTGO Vintage Cube", 540)]


# Two token-making cards: "maker1" makes Treasure and Goblin Shaman, "maker2" the Monarch.
TOKENS = {
    "tokens": {label: {"Name": "Card", "Nickname": label, "GMNotes": json.dumps({"token": label})}
               for label in ("Treasure", "Goblin Shaman 2/2 Red", "The Monarch")},
    "makers": {"maker1": ["Treasure", "Goblin Shaman 2/2 Red"], "maker2": ["The Monarch"]},
}


# ------------------------------------------------------------------ rules engine


def new_core(lua: LuaRuntime, first: str = "White"):
    return lua.eval('function(first) return DraftCore.new({colors={"White","Red"}, firstStarter=first}) end')(first)


def pick(core, color, card_id):
    """Call DraftCore:pick and normalise its return to (actions, error)."""
    res = core.pick(core, color, card_id)
    if isinstance(res, tuple):
        return res
    return res, None


class FakeTable:
    """Plays the adapter's role for the pure engine: deals ids into the pack."""

    def __init__(self, core) -> None:
        self.core = core
        self.next_id = 0
        self.dealt = 0
        self.deal_log: list[tuple[str, int]] = []

    def run(self, actions) -> None:
        for a in _to_py(actions):
            if a["type"] == "deal":
                self.deal_log.append((a["to"], a["count"]))
                for _ in range(a["count"]):
                    self.next_id += 1
                    self.dealt += 1
                    self.core.addToPack(self.core, f"c{self.next_id}")


def test_full_draft_follows_pick_order_and_counts() -> None:
    lua = make_lua()
    core = new_core(lua, "White")
    table = FakeTable(core)
    table.run(core.start(core))

    order: list[str] = []
    while not core.finished:
        picker = core.picker(core)
        pack = list(_to_py(core.pack))
        assert len(pack) == 5, "every pick is made from 5 cards"
        order.append(picker)
        actions, err = pick(core, picker, pack[0])
        assert err is None
        table.run(actions)

    assert core.pickCount(core, "White") == 48
    assert core.pickCount(core, "Red") == 48
    assert table.dealt == 24 * 8 == 192
    assert len(_to_py(core.discards)) == 24 * 4
    # Pack 1 starts with White (W R R W), pack 2 with Red (R W W R), and so on.
    assert order[:8] == ["White", "Red", "Red", "White", "Red", "White", "White", "Red"]
    assert len(order) == 96


def test_rejects_out_of_turn_and_foreign_cards() -> None:
    lua = make_lua()
    core = new_core(lua, "Red")
    table = FakeTable(core)
    table.run(core.start(core))
    card = _to_py(core.pack)[0]

    actions, err = pick(core, "White", card)
    assert actions is None and "Red's pick" in err
    actions, err = pick(core, "Red", "not-a-card")
    assert actions is None and "not in the current pack" in err


def test_refuses_pick_until_pack_is_refilled() -> None:
    lua = make_lua()
    core = new_core(lua)
    table = FakeTable(core)
    table.run(core.start(core))
    pick(core, "White", _to_py(core.pack)[0])  # deliberately skip the refill deal
    actions, err = pick(core, "Red", _to_py(core.pack)[0])
    assert actions is None and "fill back up" in err


def test_serialize_restore_round_trip() -> None:
    lua = make_lua()
    core = new_core(lua)
    table = FakeTable(core)
    table.run(core.start(core))
    for _ in range(5):
        table.run(pick(core, core.picker(core), _to_py(core.pack)[0])[0])
    restored = lua.globals().DraftCore.restore(core.serialize(core))
    assert restored.status(restored) == core.status(core)
    assert restored.picker(restored) == core.picker(core)


# ------------------------------------------------------------------ table adapter


def _play(lua: LuaRuntime, picks: int) -> None:
    g = lua.globals()
    for _ in range(picks):
        holder = g.Mock.packHolder()
        cards = _lua_list(g.Mock.packCards(holder))
        assert len(cards) == 5, f"{holder} should hold a 5-card pack"
        g.onDraftButton(cards[0], holder)  # the on-card Draft button
        g.Mock.flush()


def _lua_list(t) -> list:
    return [t[i] for i in range(1, len(t) + 1)]


def test_table_adapter_runs_a_whole_draft() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    assert g.Mock.ui["startButton.active"] == "true"

    g.onStartClicked(g.Player.White)
    g.Mock.flush()
    assert g.Mock.ui["startButton.active"] == "false"
    for color in ("White", "Red"):
        cam = g.Player[color].camera
        assert cam is not None and cam.distance > 0
    assert g.Player.White.camera.position.z < 0 < g.Player.Red.camera.position.z

    # Each camera looks down at its own pack row; hand zones sit past the pick grid.
    grid_far_edge = g.PICK_GRID_Z + 3 * 3.06 * g.PICK_SCALE * 1.05 + 3.06 * g.PICK_SCALE / 2
    for color, hand_guid in (("White", "a00001"), ("Red", "a00002")):
        assert abs(g.Mock.objects[hand_guid].pos.z) > grid_far_edge
        cam = g.Player[color].camera
        assert abs(abs(cam.position.z) - g.PACK_ROW_Z) < 2

    holder = g.Mock.packHolder()
    other = "Red" if holder == "White" else "White"
    pack = _lua_list(g.Mock.packCards(holder))
    assert all(c.rot.z == 0 for c in pack), "pack cards are face-up for their holder"
    card = pack[0]
    card.menu[1].fn(other)  # opponent tries to draft from someone else's pack
    assert any("not yours" in m for m in _lua_list(g.Mock.messages))

    _play(lua, 96)
    assert g.Mock.ui["statusText"].startswith("Deck building")
    assert len(g.Mock.objects["c00001"].cards) == 515 - 192

    # When the draft ends, all 48 picks go into the deck columns (deck editor).
    picks = _deck_cards(g)
    white = [o for o in picks if o.pos.z < 0]
    red = [o for o in picks if o.pos.z > 0]
    assert len(white) == 48 and len(red) == 48
    assert g.Mock.ui["deckText_White"].startswith("Deck 48 ")
    assert not any(o.locked for o in picks), "cards can be dragged while deck building"
    for color, mine in (("White", white), ("Red", red)):
        other = "Red" if color == "White" else "White"
        for o in mine:
            assert o.scale.x == g.DECK_SCALE
            hidden_from = set(_lua_list(o.invisibleTo))
            assert other in hidden_from and "Grey" in hidden_from and color not in hidden_from


def test_table_adapter_survives_save_and_reload_mid_draft() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    g.onStartClicked(g.Player.Red)
    g.Mock.flush()
    _play(lua, 7)

    saved = g.onSave()
    for o in g.Mock.objects.values():  # a reload drops context menus
        o.menu = lua.table()
    g.onLoad(saved)
    g.Mock.flush()
    _play(lua, 96 - 7)
    assert g.Mock.ui["statusText"].startswith("Deck building")


def test_pack_is_laid_out_on_the_table_for_its_holder_only() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    g.onStartClicked(g.Player.White)
    g.Mock.flush()
    holder = g.Mock.packHolder()
    other = "Red" if holder == "White" else "White"
    pack = _lua_list(g.Mock.packCards(holder))
    assert len(pack) == 5
    # Side by side on the holder's pack row, face-up, enlarged, not overlapping.
    xs = sorted(c.pos.x for c in pack)
    card_w = 2.2 * g.PACK_SCALE
    assert all(b - a > card_w for a, b in itertools.pairwise(xs)), "pack cards overlap"
    assert abs(sum(xs) / 5) < 0.01, "pack row is centred"
    assert all(abs(abs(c.pos.z) - g.PACK_ROW_Z) < 0.01 and c.rot.z == 0 and c.locked for c in pack)
    # The opponent sees only card backs; the holder sees the faces.
    for c in pack:
        hidden = set(_lua_list(c.hiddenFrom))
        assert other in hidden and holder not in hidden
    # Pack row sits between the middle strip (cube, discard pile) and the pick grid.
    pack_far_edge = g.PACK_ROW_Z + 3.06 * g.PACK_SCALE / 2
    grid_near_edge = g.PICK_GRID_Z - 3.06 * g.PICK_SCALE / 2
    assert g.PACK_ROW_Z - 3.06 * g.PACK_SCALE / 2 > 3.06 / 2 and pack_far_edge < grid_near_edge


def test_ui_xml_is_well_formed_and_unescaped() -> None:
    import xml.etree.ElementTree as ET

    xml = (LUA_DIR / "ui.xml").read_text(encoding="utf-8")
    root = ET.fromstring(f"<root>{xml}</root>")
    ids = {el.get("id") for el in root.iter()}
    assert {"statusText", "startButton", "resetViewButton"} <= ids
    assert "&gt;" not in xml and "&lt;" not in xml  # TTS shows entities literally


def _start_vs_bot(lua: LuaRuntime) -> None:
    g = lua.globals()
    g.Mock.setup(515)
    g.Player.Red.seated = False
    g.onLoad("")
    g.Mock.flush()
    g.onStartClicked(g.Player.White)
    g.Mock.flush()  # if Red starts, the bot has already picked by now


def _human_picks(lua: LuaRuntime, n: int) -> None:
    g = lua.globals()
    for _ in range(n):
        assert g.Mock.packHolder() == "White", "between human picks the pack is always back with White"
        cards = _lua_list(g.Mock.packCards("White"))
        assert len(cards) == 5
        cards[0].menu[1].fn("White")  # right-click > Draft this card
        g.Mock.flush()


def test_empty_seat_is_drafted_by_a_bot() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    _start_vs_bot(lua)
    assert any("bot will draft" in m for m in _lua_list(g.Mock.messages))
    _human_picks(lua, 48)
    status = g.Mock.ui["statusText"]
    assert status.startswith("Deck building")
    assert g.Mock.ui["deckText_White"].startswith("Deck 48 ")


def test_bot_keeps_drafting_after_reload() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    _start_vs_bot(lua)
    _human_picks(lua, 5)
    saved = g.onSave()
    g.onLoad(saved)
    g.Mock.flush()
    _human_picks(lua, 43)
    assert g.Mock.ui["statusText"].startswith("Deck building")


def test_debug_command_prints_geometry() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    assert g.onChat("!draftdebug", g.Player.White) is False
    out = " | ".join(_lua_list(g.Mock.messages))
    assert "White hand" in out and "Red hand" in out and "feltY" in out and "MISSING" not in out


def test_picks_stay_invisible_to_opponent_after_reload() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    _start_vs_bot(lua)
    _human_picks(lua, 3)
    saved = g.onSave()
    for o in g.Mock.objects.values():  # simulate TTS forgetting visibility on reload
        o.invisibleTo = None
    g.onLoad(saved)
    g.Mock.flush()
    picks = [o for o in g.Mock.objects.values() if o.kind == "Card" and o.scale.x == g.PICK_SCALE]
    assert len(picks) >= 6  # the bot may have picked again after the reload
    assert all(o.invisibleTo is not None for o in picks)


def test_draftauto_command_finishes_the_draft_against_a_bot() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    _start_vs_bot(lua)
    assert g.onChat("!draftauto", g.Player.White) is False
    g.Mock.flush()
    assert g.Mock.ui["statusText"].startswith("Deck building")


# ------------------------------------------------------------------ deck editor


def _deck_cards(g) -> list:
    return [o for o in g.Mock.objects.values() if o.kind == "Card" and '"id"' in o.notes and abs(o.pos.z) > 1]


def _finished_vs_bot(lua: LuaRuntime):
    g = lua.globals()
    _start_vs_bot(lua)
    _human_picks(lua, 48)
    return g


def _owner_u(o) -> float:
    """x relative to White (negative = White's left = deck side)."""
    return o.pos.x


def test_deck_editor_sorts_picks_into_mana_value_columns() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    white = [o for o in _deck_cards(g) if o.pos.z < 0]
    assert all(_owner_u(o) < g.SIDE_SPLIT_U for o in white), "every pick starts in the deck"
    # Random bot picks can leave a mana value empty, so check the grid, not the cards' extent.
    grid = [g.AREAS.main.u0 + c * g.AREAS.main.step for c in range(g.DECK_COLS)]
    assert abs(grid[0] + grid[-1]) < 0.01, "the deck's columns are centred on the middle of the table"
    assert all(any(abs(o.pos.x - x) < 0.01 for x in grid) for o in white), "every card sits in a column"
    by_x: dict[float, list] = {}
    for o in white:
        by_x.setdefault(round(o.pos.x, 2), []).append(o)
    for column in by_x.values():
        infos = [json.loads(o.notes) for o in column]
        keys = {"land" if i["land"] else min(int(i["cmc"]), 7) for i in infos}
        assert len(keys) == 1, "a column holds one mana value (or lands)"
        zs = sorted(abs(o.pos.z) for o in column)
        steps = [round(b - a, 2) for a, b in itertools.pairwise(zs)]
        assert all(step == g.DECK_CASCADE for step in steps), "cards cascade so each name shows"
    land_col = next(c for c in by_x.values() if json.loads(c[0].notes)["land"])
    assert max(o.pos.x for o in white) == land_col[0].pos.x, "lands are the rightmost deck column"


def test_dragging_to_the_sideboard_and_back_updates_counts() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    card = next(o for o in _deck_cards(g) if o.pos.z < 0)
    card.setPosition(lua.table(x=12, y=2, z=-6))  # White drops it on their right: sideboard
    g.onObjectDrop("White", card)
    g.Mock.flush()
    assert card.pos.x > g.SIDE_SPLIT_U and card.pos.z < 0 and card.scale.x == g.AREAS.side.scale
    assert g.Mock.ui["deckText_White"].startswith("Deck 47 ") and g.Mock.ui["deckText_White"].endswith("Sideboard 1")
    card.setPosition(lua.table(x=-10, y=2, z=-6))  # and back into the deck
    g.onObjectDrop("White", card)
    g.Mock.flush()
    assert g.Mock.ui["deckText_White"].startswith("Deck 48 ") and g.Mock.ui["deckText_White"].endswith("Sideboard 0")


def _lands(g, color: str = "White") -> int:
    return int(g.Mock.ui[f"deckText_{color}"].split("+ ")[1].split(" lands")[0])


def test_land_buttons_add_and_remove_basics() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    assert not [o for o in g.Mock.objects.values() if o.kind == "Infinite_Bag"], "no land bags on the table"
    lands_before = _lands(g)
    assert g.Mock.ui["land_White_Plains"] == "Plains  0"

    for _ in range(3):
        g.onLandClicked(g.Player.White, "-1", "land_White_Plains")  # left click adds
    g.Mock.flush()
    assert g.Mock.ui["deckText_White"].startswith("Deck 51 ") and _lands(g) == lands_before + 3
    assert g.Mock.ui["land_White_Plains"] == "Plains  3"
    plains = [o for o in g.Mock.objects.values() if o.kind == "Card" and o.name == "Plains"]
    assert len(plains) == 3 and all(o.pos.z < 0 and "Red" in set(_lua_list(o.invisibleTo)) for o in plains)
    land_col_x = max(o.pos.x for o in _deck_cards(g) if o.pos.z < 0 and o.pos.x < g.SIDE_SPLIT_U)
    assert all(o.pos.x == land_col_x for o in plains), "added to the Lands column"

    g.onLandClicked(g.Player.White, "-2", "land_White_Plains")  # right click removes
    g.Mock.flush()
    assert g.Mock.ui["land_White_Plains"] == "Plains  2" and g.Mock.ui["deckText_White"].startswith("Deck 50 ")

    g.onLandClicked(g.Player.Red, "-1", "land_White_Plains")  # someone else's button does nothing
    g.Mock.flush()
    assert g.Mock.ui["land_White_Plains"] == "Plains  2"


def test_a_basic_dragged_to_the_sideboard_is_removed() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    g.onLandClicked(g.Player.White, "-1", "land_White_Island")
    g.Mock.flush()
    island = next(o for o in g.Mock.objects.values() if o.kind == "Card" and o.name == "Island")
    island.setPosition(lua.table(x=15, y=2, z=-8))
    g.onObjectDrop("White", island)
    g.Mock.flush()
    assert g.Mock.objects[island.guid] is None
    assert g.Mock.ui["land_White_Island"] == "Island  0" and g.Mock.ui["deckText_White"].endswith("Sideboard 0")


def test_cards_do_not_merge_into_piles_while_deck_building() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    a, b = [o for o in _deck_cards(g) if o.pos.z < 0][:2]
    assert g.tryObjectEnterContainer(b, a) is False


def test_deck_editor_resumes_after_reload() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    saved = g.onSave()
    g.onLoad(saved)
    g.Mock.flush()
    assert g.Mock.ui["statusText"].startswith("Deck building")
    assert g.Mock.ui["deckText_White"].startswith("Deck 48 ")


def test_deck_editor_cards_float_flat_in_cascade_order() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    white = [o for o in _deck_cards(g) if o.pos.z < 0]
    assert all(o.use_gravity is False and o.rot.x == 0 and o.rot.z == 0 for o in white)
    assert all(o.sticky is False for o in white), "lifting a card must not drag the rest of its column"
    by_x: dict[float, list] = {}
    for o in white:
        by_x.setdefault(round(o.pos.x, 2), []).append(o)
    for column in by_x.values():
        # Each card nearer the player (further down the cascade) sits higher, so it is drawn on top.
        ordered = sorted(column, key=lambda o: abs(o.pos.z))
        heights = [o.pos.y for o in ordered]
        assert heights == sorted(heights) and len(set(heights)) == len(heights)


# ------------------------------------------------------------------ ready & play


def _move_to_sideboard(lua: LuaRuntime, g, cards: list) -> None:
    for c in cards:
        c.setPosition(lua.table(x=12, y=2, z=-6))
        g.onObjectDrop("White", c)
    g.Mock.flush()


def test_ready_refuses_a_deck_under_40_cards() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    white = [o for o in _deck_cards(g) if o.pos.z < 0]
    _move_to_sideboard(lua, g, white[:9])  # 48 -> 39
    g.onReadyClicked(g.Player.White)
    g.Mock.flush()
    assert any("needs at least 40" in m for m in _lua_list(g.Mock.messages))
    assert g.Mock.ui["ready_White.active"] == "true", "still building"


def test_ready_builds_library_and_sideboard_then_sets_up_the_game() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    white = [o for o in _deck_cards(g) if o.pos.z < 0]
    _move_to_sideboard(lua, g, white[:3])  # deck 45, sideboard 3
    g.onReadyClicked(g.Player.White)
    g.Mock.flush()

    decks = {o.name: o for o in g.Mock.objects.values() if o.kind == "Deck" and o.name.endswith(("library", "sideboard"))}
    assert set(decks) == {"White library", "White sideboard", "Red library"}, "the bot readied up too"
    lib, side = decks["White library"], decks["White sideboard"]
    assert len(_lua_list(lib.cards)) == 45 - 7 and lib.shuffled == 1
    assert len(_lua_list(side.cards)) == 3 and "Red" in set(_lua_list(side.invisibleTo))
    assert lib.pos.z < 0 and side.pos.z < 0
    assert g.Mock.dealt.White == 7 and g.Mock.dealt.Red == 7

    counters = [o for o in g.Mock.objects.values() if o.kind == "Counter"]
    assert sorted(c.name for c in counters) == ["Red life", "White life"]
    assert all(c.counterValue == 20 for c in counters)
    assert not [o for o in g.Mock.objects.values() if o.kind == "Infinite_Bag"], "land bags cleared away"
    assert abs(g.Mock.objects["c00001"].pos.x) > 20, "cube moved off the play area"
    middle = [o for o in g.Mock.objects.values()
              if o.kind in ("Deck", "Card") and abs(o.pos.z) < 2.5 and abs(o.pos.x) < 12]
    assert middle == [], "nothing is left in the middle"
    assert g.Mock.ui["statusPanel.active"] == "false", "the status bar is gone once the game starts"
    assert g.Mock.ui["deck_White.active"] == "false" and g.Mock.ui["ready_White.active"] == "false"


def test_deck_building_choices_survive_a_reload() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    white = [o for o in _deck_cards(g) if o.pos.z < 0]
    _move_to_sideboard(lua, g, white[:5])
    saved = g.onSave()
    g.onLoad(saved)
    g.Mock.flush()
    assert g.Mock.ui["deckText_White"].startswith("Deck 43 ") and g.Mock.ui["deckText_White"].endswith("Sideboard 5")


def test_game_state_survives_a_reload() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    g.onReadyClicked(g.Player.White)
    g.Mock.flush()
    saved = g.onSave()
    g.onLoad(saved)
    g.Mock.flush()
    assert g.Mock.ui["statusPanel.active"] == "false"
    assert len([o for o in g.Mock.objects.values() if o.kind == "Counter"]) == 2, "no duplicate counters"


# ------------------------------------------------------------------ privacy after moves


def _picks_of(g, color: str) -> list:
    sign = -1 if color == "White" else 1
    return [o for o in g.Mock.objects.values()
            if o.kind == "Card" and o.scale.x == g.PICK_SCALE and o.pos.z * sign > 0]


def _hidden_from_red(o) -> bool:
    return o.invisibleTo is not None and "Red" in set(_lua_list(o.invisibleTo))


def test_picks_moved_mid_draft_stay_hidden() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    _start_vs_bot(lua)
    _human_picks(lua, 4)
    card = _picks_of(g, "White")[0]
    card.invisibleTo = None  # TTS dropped the invisibility while it was held
    g.onObjectPickUp("White", card)
    assert _hidden_from_red(card)
    card.invisibleTo = None
    g.onObjectDrop("White", card)
    g.Mock.flush()
    assert _hidden_from_red(card)


def test_deck_editor_cards_moved_stay_hidden() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    card = next(o for o in _deck_cards(g) if o.pos.z < 0)
    card.invisibleTo = None
    g.onObjectPickUp("White", card)
    assert _hidden_from_red(card)


def test_flipped_double_faced_pick_stays_hidden_and_tracked() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    _start_vs_bot(lua)
    _human_picks(lua, 2)
    old = _picks_of(g, "White")[0]
    flipped = g.Mock.newObject("flip01", "Card")  # TTS replaces the object on a state change
    flipped.pos = old.pos
    g.Mock.objects[old.guid] = None
    g.onObjectStateChange(flipped, old.guid)
    g.Mock.flush()
    assert _hidden_from_red(flipped)
    assert '"flip01"' in g.onSave(), "the pick list follows the flipped card"


def test_hide_command_rehides_everything() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    white = [o for o in _deck_cards(g) if o.pos.z < 0]
    for o in white:
        o.invisibleTo = None
    assert g.onChat("!hide", g.Player.White) is False
    assert all(_hidden_from_red(o) for o in white)


# ------------------------------------------------------------------ tokens


def _maker(lua: LuaRuntime, guid: str, card_id: str, x: float, z: float):
    """A card that makes tokens appearing on the table (drawn, dealt or played)."""
    g = lua.globals()
    card = g.Mock.newObject(guid, "Card")
    card.notes = json.dumps({"id": card_id, "cmc": 2, "land": False, "basic": False})
    card.pos = lua.table(x=x, y=1.2, z=z)
    g.onObjectSpawn(card)
    g.Mock.flush()
    return card


def _tokens(g, label: str) -> list:
    return [o for o in g.Mock.objects.values() if o.kind == "Card" and json.loads(o.notes or "{}").get("token") == label]


def _in_game(lua: LuaRuntime):
    g = _finished_vs_bot(lua)
    g.onReadyClicked(g.Player.White)
    g.Mock.flush()
    return g


def test_right_click_creates_the_cards_tokens_beside_it() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    card = _maker(lua, "m00001", "maker1", x=0, z=-6)
    labels = [item.label for item in _lua_list(card.menu)]
    assert labels == ["Create Treasure", "Create Goblin Shaman 2/2 Red", "Put on bottom of library"]

    card.menu[1].fn("White")
    g.Mock.flush()
    (first,) = _tokens(g, "Treasure")
    assert first.name == "Treasure" and first.rot.z == 0, "face-up"
    assert first.pos.x > card.pos.x and abs(first.pos.z - card.pos.z) < 0.01, "first one on White's right"

    for _ in range(2):
        card.menu[1].fn("White")
    g.Mock.flush()
    treasures = _tokens(g, "Treasure")
    assert len(treasures) == 3
    _assert_no_overlap(g, [card, *treasures])

    plain = _maker(lua, "m00002", "not-a-maker", x=12, z=-6)
    assert [item.label for item in _lua_list(plain.menu)] == ["Put on bottom of library"], "no token entries"


def _assert_no_overlap(g, objs: list) -> None:
    for a, b in itertools.combinations(objs, 2):
        apart = abs(a.pos.x - b.pos.x) >= 2.2 or abs(a.pos.z - b.pos.z) >= 3.06
        assert apart, f"{a.name} at {a.pos.x:.1f},{a.pos.z:.1f} overlaps {b.name} at {b.pos.x:.1f},{b.pos.z:.1f}"


def test_tokens_never_land_on_other_cards_and_stay_on_your_battlefield() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    # A row of cards one card-width apart, like a real battlefield (the bug found in TTS).
    row = [_maker(lua, f"r{i:05d}", "maker1", x=-10 + 3 * i, z=-7) for i in range(7)]
    for card in row:
        card.menu[1].fn("White")
        card.menu[2].fn("White")
    g.Mock.flush()
    tokens = _tokens(g, "Treasure") + _tokens(g, "Goblin Shaman 2/2 Red")
    assert len(tokens) == 14
    _assert_no_overlap(g, row + tokens)
    assert all(1.8 <= -t.pos.z <= 16 and abs(t.pos.x) <= 29 for t in tokens), "on White's battlefield"


def test_tokens_from_a_card_in_hand_land_on_your_side() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    card = _maker(lua, "m00003", "maker1", x=0, z=19)  # in Red's hand
    card.menu[2].fn("Red")
    g.Mock.flush()
    (shaman,) = _tokens(g, "Goblin Shaman 2/2 Red")
    assert 1 < shaman.pos.z < 15, "on Red's battlefield, not in the hand"


def test_the_monarch_moves_instead_of_duplicating() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    white_card = _maker(lua, "m00004", "maker2", x=0, z=-6)
    red_card = _maker(lua, "m00005", "maker2", x=0, z=6)
    white_card.menu[1].fn("White")
    red_card.menu[1].fn("Red")
    g.Mock.flush()
    (monarch,) = _tokens(g, "The Monarch")
    assert monarch.pos.z > 0, "the Monarch moved to Red"


def test_no_token_menus_before_the_game_and_they_return_after_reload() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    _start_vs_bot(lua)
    early = _maker(lua, "m00006", "maker1", x=0, z=-6)
    assert len(_lua_list(early.menu)) == 0, "draft and deck-building menus are left alone"

    g = _in_game(make_lua(with_table=True))
    card = g.Mock.newObject("m00007", "Card")  # a reload drops every context menu
    card.notes = json.dumps({"id": "maker2", "cmc": 3, "land": False, "basic": False})
    saved = g.onSave()
    g.onLoad(saved)
    g.Mock.flush()
    assert [item.label for item in _lua_list(card.menu)] == ["Create The Monarch", "Put on bottom of library"]


# ------------------------------------------------------------------ booster tutor


def _booster(g) -> list:
    return sorted((o for o in g.Mock.objects.values() if o.kind == "Card" and len(o.buttons) > 0),
                  key=lambda o: o.pos.x)


def test_booster_tutor_opens_15_cards_and_puts_the_choice_in_hand() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    cube = g.Mock.objects["c00001"]
    before = len(cube.cards)
    tutor = _maker(lua, "bt0001", "booster-tutor-id", x=0, z=-19)  # in White's hand
    tutor.name = "Booster Tutor"
    g.onObjectSpawn(tutor)
    g.Mock.flush()
    assert [item.label for item in _lua_list(tutor.menu)] == ["Open a booster", "Put on bottom of library"]

    tutor.menu[1].fn("White")
    g.Mock.flush()
    pack = _booster(g)
    assert len(pack) == 15 and len(cube.cards) == before - 15
    assert all(c.locked and c.rot.z == 0 and abs(c.pos.z) < 0.01 for c in pack), "face-up row across the middle"
    assert all(b.pos.x - a.pos.x > 2.2 * g.BOOSTER_SCALE for a, b in itertools.pairwise(pack)), "no overlap"
    assert all(not c.hiddenFrom or len(_lua_list(c.hiddenFrom)) == 0 for c in pack), "revealed to everyone"
    assert [item.label for item in _lua_list(pack[0].menu)] == ["Take this card"], "no token menu on pack cards"

    tutor.menu[1].fn("Red")  # only one booster at a time
    pack[3].menu[1].fn("Red")  # and only the opener takes from it
    g.Mock.flush()
    assert len(_booster(g)) == 15

    chosen = pack[3]
    g.onBoosterTake(chosen, "White")
    g.Mock.flush()
    hand = {o.guid for o in _lua_list(g.Player.White.getHandObjects())}
    assert chosen.guid in hand and not chosen.locked and chosen.scale.x == 1
    assert len(cube.cards) == before - 1, "the other 14 go back into the (locked) cube"
    assert cube.locked, "the cube is locked again afterwards"
    assert _booster(g) == [] and any("takes" in m for m in _lua_list(g.Mock.messages))

    tutor.menu[1].fn("Red")  # a new booster can be opened afterwards
    g.Mock.flush()
    assert len(_booster(g)) == 15


def test_open_booster_survives_a_reload() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    tutor = _maker(lua, "bt0002", "booster-tutor-id", x=0, z=-6)
    tutor.name = "Booster Tutor"
    g.onObjectSpawn(tutor)
    g.Mock.flush()
    tutor.menu[1].fn("Red")
    g.Mock.flush()
    saved = g.onSave()
    for o in g.Mock.objects.values():  # a reload drops buttons and menus
        o.buttons = lua.table()
        o.menu = lua.table()
    g.onLoad(saved)
    g.Mock.flush()
    pack = _booster(g)
    assert len(pack) == 15
    pack[0].menu[1].fn("Red")
    g.Mock.flush()
    assert pack[0].guid in {o.guid for o in _lua_list(g.Player.Red.getHandObjects())}


# ------------------------------------------------------------------ next game


def _click_next_game(g, color: str = "White") -> None:
    g.onNextGameClicked(g.Player[color])
    g.onNextGameClicked(g.Player[color])  # the second click confirms
    g.Mock.flush()


def test_next_game_returns_every_card_for_sideboarding_and_drops_booster_picks() -> None:
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    white = [o for o in _deck_cards(g) if o.pos.z < 0]
    _move_to_sideboard(lua, g, white[:3])  # deck 45, sideboard 3
    g.onReadyClicked(g.Player.White)
    g.Mock.flush()
    assert g.Mock.ui["nextGameButton.active"] == "true"
    cube = g.Mock.objects["c00001"]

    # Mid-game: a card on the battlefield, a token beside it, and a Booster Tutor pick in hand.
    lib = next(o for o in g.Mock.objects.values() if o.kind == "Deck" and o.name == "White library")
    played = lib.takeObject(lua.table(position=lua.table(x=0, y=1, z=-6)))
    g.createToken("White", "Treasure", played)
    g.openBooster("White")
    g.Mock.flush()
    pick = _booster(g)[0]
    g.onBoosterTake(pick, "White")
    g.Mock.flush()
    assert pick.guid in {o.guid for o in _lua_list(g.Player.White.getHandObjects())}
    cube_before = len(cube.cards)

    g.onNextGameClicked(g.Player.White)
    g.onNextGameClicked(g.Player.White)
    # While cards are on their way back they must not merge into piles (found in TTS).
    in_hand = _lua_list(g.Player.White.getHandObjects())
    assert g.tryObjectEnterContainer(in_hand[0], played) is False
    g.Mock.flush()
    assert g.Mock.ui["statusText"].startswith("Sideboarding for game 2")
    assert g.Mock.ui["deckText_White"].startswith("Deck 45 ") and g.Mock.ui["deckText_White"].endswith("Sideboard 3")
    assert g.Mock.ui["deckText_Red"].startswith("Deck 48 ")
    assert g.Mock.objects[pick.guid] is None and len(cube.cards) == cube_before + 1, "the pick went back to the cube"
    assert _tokens(g, "Treasure") == [], "tokens are removed"
    assert not [o for o in g.Mock.objects.values() if o.kind == "Counter"], "life counters are removed"
    assert not [o for o in g.Mock.objects.values() if o.kind == "Deck" and o.guid != "c00001"
                and o.name.endswith(("library", "sideboard"))], "libraries and sideboards are emptied"
    mine = [o for o in _deck_cards(g) if o.pos.z < 0]
    assert len(mine) == 48 and all(not o.locked and _hidden_from_red(o) for o in mine)
    assert g.Mock.ui["nextGameButton.active"] == "false" and g.Mock.ui["ready_White.active"] == "true"

    saved = g.onSave()  # a reload during sideboarding keeps the game number
    g.onLoad(saved)
    g.Mock.flush()
    assert g.Mock.ui["statusText"].startswith("Sideboarding for game 2")

    g.onReadyClicked(g.Player.White)  # game 2 starts as before
    g.Mock.flush()
    assert g.Mock.dealt.White == 14 and g.Mock.ui["statusPanel.active"] == "false"
    assert len([o for o in g.Mock.objects.values() if o.kind == "Counter"]) == 2


def test_next_game_needs_a_confirming_second_click() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    g.onNextGameClicked(g.Player.White)
    g.Mock.flush()  # the confirmation times out
    g.onNextGameClicked(g.Player.White)
    assert g.Mock.ui["nextGameButton.text"] == "Click again to confirm"
    assert g.Mock.ui["statusPanel.active"] == "false", "still playing after single clicks"


# ------------------------------------------------------------------ playmats


def _mats(g) -> list:
    return [o for o in g.Mock.objects.values() if o.kind == "Custom_Tile" and "playmat" in o.name]


def _pick(g, color: str, index: int, as_color: str | None = None) -> None:
    """Opens the seat's picker with its button, then clicks thumbnail ``index`` (0 = None)."""
    player = g.Player[as_color or color]
    g.onMatButton(player, "-1", f"matButton_{color}")
    g.onMatPick(player, "-1", f"matPick_{color}_{index}")
    g.Mock.flush()


def test_players_choose_replace_and_remove_their_playmat() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    assert g.Mock.ui["matButton_White.text"] == "Playmat: None"

    g.onMatButton(g.Player.White, "-1", "matButton_White")
    assert g.Mock.ui["matPicker_White.active"] == "true", "the button opens the picker"
    g.onMatPick(g.Player.White, "-1", "matPick_White_1")  # Volcano
    g.Mock.flush()
    assert g.Mock.ui["matPicker_White.active"] == "false", "picking closes it"
    assert g.Mock.ui["matButton_White.text"] == "Playmat: Volcano"
    (mat,) = _mats(g)
    assert mat.custom.image == "https://h/Volcano.jpg" and mat.name == "White playmat: Volcano"
    assert mat.pos.z < 0 and mat.locked and mat.interactable is False, "locked under White's half"
    assert mat.pos.y < 1.1, "flat on the felt, under the cards"
    assert mat.scale.x == mat.scale.z == 8, "2-unit-deep tile scaled to 16 deep (44 wide)"

    _pick(g, "White", 2)  # Aurora replaces Volcano, never stacks
    _pick(g, "Red", 1)
    assert sorted((m.name, m.pos.z > 0) for m in _mats(g)) == [
        ("Red playmat: Volcano", True), ("White playmat: Aurora", False)]

    _pick(g, "White", 1, as_color="Red")  # someone else's picker does nothing
    assert any(m.name == "White playmat: Aurora" for m in _mats(g))

    g.onMatButton(g.Player.White, "-1", "matButton_White")
    g.onMatButton(g.Player.White, "-1", "matClose_White")
    assert g.Mock.ui["matPicker_White.active"] == "false", "Close closes it"

    _pick(g, "White", 0)
    assert [m.name for m in _mats(g)] == ["Red playmat: Volcano"]
    assert g.Mock.ui["matButton_White.text"] == "Playmat: None"


def test_playmat_survives_a_reload_and_ignores_the_game() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    _pick(g, "White", 1)
    (mat,) = _mats(g)
    saved = g.onSave()
    mat.interactable = True  # TTS does not save this
    g.Mock.ui["matButton_White.text"] = "Playmat: None"  # nor the UI's labels
    g.onLoad(saved)
    g.Mock.flush()
    assert mat.interactable is False
    assert g.Mock.ui["matButton_White.text"] == "Playmat: Volcano", "the button shows the mat after a reload"
    _pick(g, "White", 2)  # the reloaded mat is still tracked
    assert [m.name for m in _mats(g)] == ["White playmat: Aurora"]

    g.onNextGameClicked(g.Player.White)
    g.onNextGameClicked(g.Player.White)
    g.Mock.flush()
    assert len(_mats(g)) == 1, "Next game leaves the playmat alone"


# ------------------------------------------------------------------ zones, draw, untap, dice


def _boards(g) -> dict:
    return {o.name: o for o in g.Mock.objects.values() if o.kind == "Custom_Tile" and o.name.endswith(" zones")}


def _library(g, color: str = "White"):
    return next(o for o in g.Mock.objects.values() if o.kind == "Deck" and o.name == f"{color} library")


def _button(board, label: str):
    return next(b for b in _lua_list(board.buttons) if b.label == label)


def _dice(g) -> list:
    return [o for o in g.Mock.objects.values() if o.kind.startswith("Die_")]


def test_each_seat_gets_a_zone_board_with_its_library_in_the_slot() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    boards = _boards(g)
    assert set(boards) == {"White zones", "Red zones"}
    white, red = boards["White zones"], boards["Red zones"]
    assert white.locked and white.custom.image == "https://h/zones.jpg"
    assert white.scale.z == zones.BOARD["h"] / 2, "a tile is 2 units deep at scale 1"
    # On each owner's right: +x for White (at -z), -x for Red.
    assert abs(white.pos.x - zones.BOARD["u"]) < 1e-6 and abs(white.pos.z + zones.BOARD["d"]) < 1e-6
    assert abs(red.pos.x + zones.BOARD["u"]) < 1e-6 and abs(red.pos.z - zones.BOARD["d"]) < 1e-6
    assert white.pos.y > 0.96 + g.MAT_THICKNESS, "on top of a playmat"
    assert [b.label for b in _lua_list(white.buttons)] == ["Untap", "Draw", "Mulligan", "Scry", "Surveil"]
    assert _button(white, "Draw").click_function == "onZoneDraw"
    for color, sign in (("White", 1), ("Red", -1)):
        lib = _library(g, color)
        assert abs(lib.pos.x - sign * zones.BOARD["u"]) < 1e-6
        assert abs(lib.pos.z + sign * zones.SLOTS["library"]["d"]) < 1e-6


def test_draw_button_draws_for_its_owner_until_the_library_is_empty() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    white = _boards(g)["White zones"]
    g.onZoneDraw(white, "Red")
    assert g.Mock.dealt.White == 7 and any("White's board" in m for m in _lua_list(g.Mock.messages))
    g.onZoneDraw(white, "White")
    assert g.Mock.dealt.White == 8 and len(_library(g).cards) == 48 - 8
    for _ in range(40):  # the last card is no longer a deck: it is found in the library slot
        g.onZoneDraw(white, "White")
    assert len(_lua_list(g.Player.White.getHandObjects())) == 48
    g.onZoneDraw(white, "White")
    assert any("library is empty" in m for m in _lua_list(g.Mock.messages))


def test_untap_button_straightens_only_your_tapped_cards() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    lib = _library(g)

    def played(x: float, z: float, yaw: float, flip: float = 0, locked: bool = False):
        card = lib.takeObject(lua.table(position=lua.table(x=x, y=1.2, z=z)))
        card.rot = lua.table(x=0, y=yaw, z=flip)
        card.locked = locked
        return card

    tapped = played(0, -6, 90)
    tapped_down = played(-4, -6, 270, flip=180)  # a face-down card (a morph) tapped the other way
    upright = played(4, -6, 180)
    theirs = played(0, 6, 90)  # tapped on Red's side
    booster = played(8, -1, 90, locked=True)
    g.onZoneUntap(_boards(g)["Red zones"], "White")  # not White's board: nothing happens
    assert tapped.rot.y == 90
    g.onZoneUntap(_boards(g)["White zones"], "White")
    assert (tapped.rot.y, tapped.rot.z) == (180, 0)
    assert (tapped_down.rot.y, tapped_down.rot.z) == (180, 180), "face-down stays face-down"
    assert upright.rot.y == 180 and theirs.rot.y == 90 and booster.rot.y == 90


def test_zone_boards_survive_a_reload_and_leave_for_sideboarding() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    saved = g.onSave()
    for board in _boards(g).values():
        board.buttons = lua.table()  # TTS does not save buttons
    g.onLoad(saved)
    g.Mock.flush()
    boards = _boards(g)
    assert len(boards) == 2 and all(len(_lua_list(b.buttons)) == 5 for b in boards.values())
    g.onZoneDraw(boards["White zones"], "White")
    assert g.Mock.dealt.White == 8, "the reloaded board still draws"

    _click_next_game(g)
    assert _boards(g) == {}, "the sideboard columns need that edge of the table"
    g.onReadyClicked(g.Player.White)
    g.Mock.flush()
    assert set(_boards(g)) == {"White zones", "Red zones"}


def test_tokens_are_not_created_on_a_zone_board() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    card = _maker(lua, "m00001", "maker1", x=16.6, z=-10)
    for _ in range(4):
        card.menu[1].fn("White")
    g.Mock.flush()
    b = zones.BOARD
    for t in _tokens(g, "Treasure"):
        clear = abs(t.pos.x - b["u"]) >= (b["w"] + 2.2) / 2 or abs(t.pos.z + b["d"]) >= (b["h"] + 3.06) / 2
        assert clear, f"token at {t.pos.x:.1f},{t.pos.z:.1f} is on the board"


def test_each_seat_has_its_dice_from_the_start_and_never_twice() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    dice = _dice(g)
    assert sorted(d.name for d in dice) == ["Red d20", "Red d6", "Red d6", "White d20", "White d6", "White d6"]
    white = [d for d in dice if d.name.startswith("White")]
    assert all(d.pos.z < -10 and d.pos.x < -22 for d in white), "White's left corner, off the playmat"
    assert all(d.tint.name == "White" for d in white)
    g.onLoad(g.onSave())
    g.Mock.flush()
    assert len(_dice(g)) == 6, "a reload keeps the same dice"


# ------------------------------------------------------------------ cubes


def _cube_decks(g) -> list:
    return [o for o in g.Mock.objects.values() if o.kind == "Deck" and o.cards is not None and len(o.cards) >= 300]


def _choose_cube(g, color: str, index: int, as_color: str | None = None) -> None:
    """Opens the seat's cube picker with its button, then clicks cube ``index`` (1-based)."""
    player = g.Player[as_color or color]
    g.onCubeButton(player, "-1", f"cubeButton_{color}")
    g.onCubePick(player, "-1", f"cubePick_{color}_{index}")
    g.Mock.flush()


def test_players_switch_the_cube_before_the_draft() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    assert g.Mock.ui["cubeButton_White.text"] == "Cube: LSV Cube"
    assert g.Mock.ui["cubeButton_Red.active"] == "true"
    assert "Cube: LSV Cube" in g.Mock.ui["statusText"]

    _choose_cube(g, "White", 2, as_color="Red")  # someone else's picker does nothing
    assert g.Mock.spawnedJSON is None and g.Mock.objects["c00001"] is not None

    old = g.Mock.objects["c00001"]
    old_place = (old.pos.x, old.pos.y, old.pos.z, old.rot.y, old.rot.z)
    g.onCubeButton(g.Player.White, "-1", "cubeButton_White")
    assert g.Mock.ui["cubePicker_White.active"] == "true", "the button opens the picker"
    g.onCubePick(g.Player.White, "-1", "cubePick_White_2")
    g.Mock.flush()
    assert g.Mock.ui["cubePicker_White.active"] == "false", "picking closes it"
    assert g.Mock.objects["c00001"] is None, "the old cube is gone"
    (deck,) = _cube_decks(g)
    assert len(deck.cards) == 540 and deck.interactable is False
    assert (deck.pos.x, deck.pos.y, deck.pos.z, deck.rot.y, deck.rot.z) == old_place, "same spot and facing"
    assert g.Mock.ui["cubeButton_Red.text"] == "Cube: MTGO Vintage Cube", "both seats see the new cube"
    assert any("White chose the MTGO Vintage Cube (540 cards)" in m for m in _lua_list(g.Mock.messages))

    _choose_cube(g, "Red", 2)  # already on the table: nothing to do
    assert g.Mock.spawnedJSON == 1

    g.onStartClicked(g.Player.White)
    g.Mock.flush()
    assert g.Mock.ui["cubeButton_White.active"] == "false", "no switching once the draft starts"
    assert any("Drafting the MTGO Vintage Cube" in m for m in _lua_list(g.Mock.messages))
    g.switchCube("lsv", "Red")
    assert any("can't change once the draft has started" in m for m in _lua_list(g.Mock.messages))
    assert [d.guid for d in _cube_decks(g)] == [deck.guid]

    _play(lua, 96)
    assert g.Mock.ui["statusText"].startswith("Deck building")
    assert len(deck.cards) == 540 - 192, "the draft dealt from the chosen cube"


def test_chosen_cube_survives_a_reload_and_the_draft_continues_from_it() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    _choose_cube(g, "Red", 2)
    (deck,) = _cube_decks(g)

    saved = g.onSave()
    g.Mock.ui["cubeButton_White.text"] = "Cube: ?"  # TTS does not save UI labels
    deck.interactable = True  # nor this
    g.onLoad(saved)
    g.Mock.flush()
    assert g.Mock.ui["cubeButton_White.text"] == "Cube: MTGO Vintage Cube"
    assert deck.interactable is False

    g.onStartClicked(g.Player.Red)
    g.Mock.flush()
    _play(lua, 7)
    saved = g.onSave()
    for o in g.Mock.objects.values():
        o.menu = lua.table()
    g.onLoad(saved)
    g.Mock.flush()
    _play(lua, 96 - 7)
    assert len(deck.cards) == 540 - 192


def test_switching_back_restores_the_first_cube() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    _choose_cube(g, "White", 2)
    _choose_cube(g, "White", 1)
    (deck,) = _cube_decks(g)
    assert len(deck.cards) == 515
    assert g.Mock.ui["cubeButton_White.text"] == "Cube: LSV Cube"


# ------------------------------------------------------------------ layout timing (seen in TTS)


def test_start_draft_works_before_the_delayed_layout_has_run() -> None:
    # In TTS, Start Draft was pressed while onLoad's delayed layout had not run: dealTo hit a nil layout.
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.onStartClicked(g.Player.White)  # before Mock.flush(): the 10-frame wait is still pending
    g.Mock.flush()
    holder = g.Mock.packHolder()
    assert len(_lua_list(g.Mock.packCards(holder))) == 5


def test_layout_ignores_a_cube_that_has_not_settled_onto_the_table() -> None:
    # A fresh save's cube was measured at y=1.2 (half inside the table), giving felt y=0.15.
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.Mock.objects["c00001"].pos.y = 1.2
    g.onLoad("")
    g.Mock.flush()
    g.onStartClicked(g.Player.White)
    g.Mock.flush()
    cards = _lua_list(g.Mock.packCards(g.Mock.packHolder()))
    assert all(c.pos.y > 0.96 for c in cards), "pack cards sit above the felt"
    dice = _dice(g)
    assert dice and all(d.pos.y > 0.96 for d in dice), "dice spawn above the felt"


def test_game_starts_when_cards_merge_into_piles_by_themselves() -> None:
    # Seen in TTS: the gathered cards merged into a deck as they landed, before the script
    # grouped them, so the piles were never named or recorded and nobody was dealt a hand.
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    white = [o for o in _deck_cards(g) if o.pos.z < 0]
    _move_to_sideboard(lua, g, white[:3])
    g.onReadyClicked(g.Player.White)
    for color, sign in (("White", 1), ("Red", -1)):  # TTS merges each library on landing
        spot = [o for o in g.Mock.objects.values() if o.kind == "Card"
                and abs(o.pos.x - sign * zones.BOARD["u"]) < 0.01 and abs(o.pos.z + sign * zones.SLOTS["library"]["d"]) < 0.01]
        assert len(spot) >= 40
        g.group(lua.table_from(spot))
    ready_at = g.Mock.now
    lua.execute("local start = startGame; startGame = function() Mock.startedAt = Mock.now; start() end")
    g.Mock.flush()
    names = {o.name for o in g.Mock.objects.values() if o.kind == "Deck"}
    assert {"White library", "White sideboard", "Red library"} <= names
    assert g.Mock.dealt.White == 7 and g.Mock.dealt.Red == 7
    assert len(_library(g).cards) == 45 - 7
    assert g.Mock.startedAt - ready_at < 2, "the game starts as soon as the piles have formed (TTS waited 10 s)"


def test_game_waits_for_slow_piles_before_dealing() -> None:
    # Seen in TTS (game 2): Red's 48 cards were still merging when the game started, so the
    # deal hit a partial pile (Red drew 2) and the library was never named.
    lua = make_lua(with_table=True)
    g = _finished_vs_bot(lua)
    g.Mock.groupLate = 30  # the cards stay loose for 3 seconds, then merge
    g.onReadyClicked(g.Player.White)
    g.Mock.flush()
    names = {o.name for o in g.Mock.objects.values() if o.kind == "Deck"}
    assert {"White library", "Red library"} <= names
    assert g.Mock.dealt.White == 7 and g.Mock.dealt.Red == 7
    assert len(_lua_list(g.Player.Red.getHandObjects())) == 7


def test_playmat_lies_on_the_felt_even_if_the_layout_was_measured_from_a_falling_cube() -> None:
    # Seen in TTS: after switching to the Vintage Cube the layout was measured while the new deck
    # was still dropping (felt read as 1.72), and the playmat picked next covered the pack and picks.
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    g.Mock.objects["c00001"].pos.y = 2.77  # the switched-in deck spawns here and is still falling
    _choose_cube(g, "White", 2)
    _pick(g, "White", 1)
    (mat,) = _mats(g)
    assert abs(mat.pos.y - (0.96 + g.MAT_THICKNESS / 2)) < 0.02, f"mat at y={mat.pos.y:.2f}, above the cards"
    g.onStartClicked(g.Player.White)
    g.Mock.flush()
    cards = _lua_list(g.Mock.packCards(g.Mock.packHolder()))
    assert all(c.pos.y > mat.pos.y + g.MAT_THICKNESS / 2 for c in cards), "pack cards lie on top of the mat"


def test_leftover_pack_cards_vanish() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    _start_vs_bot(lua)
    first_pack = {c.guid for c in _lua_list(g.Mock.packCards(g.Mock.packHolder()))}
    _human_picks(lua, 2)  # pack 1 is done once both players have picked twice
    cards = [o for o in g.Mock.objects.values() if o.kind == "Card"]
    picks = [o for o in cards if o.scale.x == g.PICK_SCALE]
    pack = _lua_list(g.Mock.packCards(g.Mock.packHolder()))
    assert len(cards) == len(picks) + len(pack), "only picks and the current pack are on the table"
    leftovers = first_pack - {o.guid for o in picks}
    assert leftovers and all(g.Mock.objects[guid] is None for guid in leftovers), "undrafted cards are gone"
    middle = [o for o in g.Mock.objects.values() if o.kind in ("Card", "Deck") and abs(o.pos.z) < 2.5 and o.guid != "c00001"]
    assert middle == [], f"no discard pile in the middle: {[(o.kind, o.guid, o.pos.x, o.pos.z) for o in middle]}"
    assert '"discard"' not in g.onSave()

    g.autoPick(200)
    g.Mock.flush()
    cards = [o for o in g.Mock.objects.values() if o.kind == "Card"]
    assert len(cards) == 96, "after the draft only the 96 drafted cards are on the table"


# ------------------------------------------------------------------ scry, surveil, mulligan


def _hand(g, color: str = "White") -> list:
    return _lua_list(g.Player[color].getHandObjects())


def _labels(obj) -> list:
    return [b.label for b in _lua_list(obj.buttons)]


def _said(g, text: str) -> bool:
    return any(text in m for m in _lua_list(g.Mock.messages))


def test_scry_surveil_and_mulligan_sit_right_of_untap_and_draw() -> None:
    g = _in_game(make_lua(with_table=True))
    btn = {b.label: b for b in _lua_list(_boards(g)["White zones"].buttons)}
    for side, beside in (("Scry", "Untap"), ("Surveil", "Draw")):
        assert btn[side].position.z == btn[beside].position.z, f"{side} on the {beside} row"
        assert btn[side].position.x > 0 and btn[beside].position.x == 0, "on the owner's right of the board"
    assert btn["Mulligan"].position.z < btn["Scry"].position.z, "above Scry, away from the sideboard pile"
    half_w = zones.BUTTONS["scry"]["w"] / 2
    assert zones.SIDE_U - half_w > zones.BOARD["u"] + zones.BOARD["w"] / 2, "clear of the board"
    assert zones.SIDE_U + half_w < zones.SIDEBOARD["u"] - 2.2 / 2, "clear of the sideboard pile"


def test_scry_shows_the_top_cards_to_their_owner_and_puts_them_on_top_or_bottom() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    white, lib = _boards(g)["White zones"], _library(g)
    top = _lua_list(lib.cards)[:2]
    g.onZoneScry(white, "Red")  # not Red's board
    assert len(lib.cards) == 41
    g.onZoneScry(white, "White")
    g.onZoneScry(white, "White")  # each click looks at one more
    looked = [g.Mock.objects[guid] for guid in top]
    assert len(lib.cards) == 39 and _said(g, "White scries 2.")
    for card in looked:
        assert card.locked and card.rot.z == 0, "face-up for White..."
        assert "Red" in set(_lua_list(card.hiddenFrom)) and "White" not in set(_lua_list(card.hiddenFrom)), \
            "...and a card back for Red"
        assert _labels(card) == ["Top", "Bottom"]
    assert looked[0].pos.x > looked[1].pos.x, "the row runs toward White's left"
    assert looked[0].pos.z < 0 and abs(looked[0].pos.z) < zones.BOARD["d"] + zones.BOARD["h"] / 2

    g.onZoneDraw(white, "White")
    assert g.Mock.dealt.White == 7 and _said(g, "back first"), "no drawing past the cards being looked at"
    g.onLookTop(looked[0], "Red")
    assert g.Mock.objects[top[0]] is not None and _said(g, "White's cards")

    g.onLookBottom(looked[0], "White")
    assert _lua_list(lib.cards)[-1] == top[0] and lib.stored[top[0]].rot.z == 180, "face-down at the bottom"
    assert abs(looked[1].pos.x - zones.LOOK["u"]) < 1e-6, "the row closes up"
    g.onLookTop(looked[1], "White")
    assert _lua_list(lib.cards)[0] == top[1] and len(lib.cards) == 41
    back = lib.stored[top[1]]
    assert not back.locked and _labels(back) == [] and _lua_list(back.hiddenFrom) == []
    g.onZoneDraw(white, "White")
    assert top[1] in {o.guid for o in _hand(g)}, "the card kept on top is drawn next"


def test_surveil_puts_cards_in_the_graveyard_or_back_on_top() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    white, lib = _boards(g)["White zones"], _library(g)
    first, second = _lua_list(lib.cards)[:2]
    g.onZoneSurveil(white, "White")
    g.onZoneSurveil(white, "White")
    a, b = g.Mock.objects[first], g.Mock.objects[second]
    assert _labels(a) == ["Top", "Graveyard"] and _said(g, "White surveils 2.")
    g.onZoneScry(white, "White")
    assert len(lib.cards) == 39 and _said(g, "Finish your surveil first")

    g.onLookGraveyard(a, "White")
    assert abs(a.pos.x - zones.BOARD["u"]) < 1e-6 and abs(a.pos.z + zones.SLOTS["graveyard"]["d"]) < 1e-6
    assert a.rot.z == 0 and not a.locked and _labels(a) == [] and _lua_list(a.hiddenFrom) == []
    g.onLookGraveyard(b, "White")
    assert b.pos.y > a.pos.y, "on top of the graveyard"
    g.onZoneScry(white, "White")  # done surveilling: scrying works again
    assert len(lib.cards) == 38


def test_mulligan_takes_a_second_click_and_only_the_second_costs_a_card() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    white, lib = _boards(g)["White zones"], _library(g)
    opening = {o.guid for o in _hand(g)}
    g.onZoneMulligan(white, "White")
    assert "Confirm?" in _labels(white) and {o.guid for o in _hand(g)} == opening
    g.Mock.flush()  # the click is forgotten after a few seconds
    assert "Mulligan" in _labels(white) and lib.shuffled == 1

    g.onZoneMulligan(white, "Red")
    g.onZoneMulligan(white, "Red")  # not Red's board
    assert lib.shuffled == 1
    g.onZoneMulligan(white, "White")
    g.onZoneMulligan(white, "White")
    assert lib.shuffled == 2 and g.Mock.dealt.White == 14
    assert len(_hand(g)) == 7 and len(lib.cards) == 41 and "Mulligan" in _labels(white)
    assert _said(g, "White takes a free mulligan and draws a new 7.") and not _said(g, "on the bottom")

    g.onZoneMulligan(white, "White")
    g.onZoneMulligan(white, "White")  # the second costs a card
    hand = _hand(g)
    assert len(hand) == 7 and _said(g, "(2 times)") and _said(g, "puts 1 card on the bottom")
    g.putOnBottom("Red", hand[0])
    assert _said(g, "That is White's card.") and len(_hand(g)) == 7
    g.addPlayMenu(hand[0])
    bottom = next(item for item in _lua_list(hand[0].menu) if item.label == "Put on bottom of library")
    bottom.fn("White")
    assert _lua_list(lib.cards)[-1] == hand[0].guid and len(_hand(g)) == 6 and _said(g, "White keeps 6.")

    g.onZoneMulligan(white, "White")
    g.onZoneMulligan(white, "White")
    assert len(_hand(g)) == 7 and _said(g, "(3 times)") and _said(g, "puts 2 cards on the bottom")


def test_cards_being_scried_survive_a_reload_and_come_back_for_sideboarding() -> None:
    lua = make_lua(with_table=True)
    g = _in_game(lua)
    white = _boards(g)["White zones"]
    g.onZoneScry(white, "White")
    g.onZoneScry(white, "White")
    looked = [o for o in g.Mock.objects.values() if o.kind == "Card" and _labels(o) == ["Top", "Bottom"]]
    assert len(looked) == 2
    saved = g.onSave()
    for o in looked:  # TTS keeps neither buttons nor visibility
        o.buttons, o.hiddenFrom, o.menu = lua.table(), lua.table(), lua.table()
    g.onLoad(saved)
    g.Mock.flush()
    for o in looked:
        assert _labels(o) == ["Top", "Bottom"] and "Red" in set(_lua_list(o.hiddenFrom))
        assert [item.label for item in _lua_list(o.menu)] == ["Put on top of library", "Put on bottom of library"]

    _click_next_game(g)
    mine = [o for o in _deck_cards(g) if o.pos.z < 0]
    assert len(mine) == 48 and all(not o.locked and _labels(o) == [] for o in mine)
    g.onReadyClicked(g.Player.White)
    g.Mock.flush()
    g.onZoneScry(_boards(g)["White zones"], "White")
    assert _said(g, "White scries 1."), "a new game starts with nothing being looked at"
