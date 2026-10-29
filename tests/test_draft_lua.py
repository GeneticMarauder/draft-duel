"""Runs the real Lua (rules engine + table adapter) under lupa with a mocked TTS API."""

from __future__ import annotations

import itertools
import json
from importlib import resources
from pathlib import Path
from typing import Any

from lupa import LuaRuntime

LUA_DIR = resources.files("lsv_duel_draft") / "lua"
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
        lua.execute((LUA_DIR / "table.lua").read_text(encoding="utf-8"))
    return lua


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
        assert len(pack) == 4, "every pick is made from 4 cards"
        order.append(picker)
        actions, err = pick(core, picker, pack[0])
        assert err is None
        table.run(actions)

    assert core.pickCount(core, "White") == 48
    assert core.pickCount(core, "Red") == 48
    assert table.dealt == 24 * 7 == 168
    assert len(_to_py(core.discards)) == 24 * 3
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
        assert len(cards) == 4, f"{holder} should hold a 4-card pack"
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
    assert len(g.Mock.objects["c00001"].cards) == 515 - 168

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
    assert len(pack) == 4
    # Side by side on the holder's pack row, face-up, enlarged, not overlapping.
    xs = sorted(c.pos.x for c in pack)
    card_w = 2.2 * g.PACK_SCALE
    assert all(b - a > card_w for a, b in itertools.pairwise(xs)), "pack cards overlap"
    assert abs(sum(xs) / 4) < 0.01, "pack row is centred"
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
    assert {"statusText", "startButton", "resetViewButton", "prompt_White", "prompt_Red"} <= ids
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
        assert len(cards) == 4
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
    xs = [o.pos.x for o in white]
    assert abs(min(xs) + max(xs)) < 0.01, "the deck's columns are centred on the middle of the table"
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
    # TTS can re-create the discard pile under a new GUID; the setup must not depend on it.
    pile = next(o for o in g.Mock.objects.values() if o.kind == "Deck" and abs(o.pos.z) < 1 and o.guid != "c00001")
    g.Mock.objects[pile.guid] = None
    pile.guid = "fresh1"
    g.Mock.objects["fresh1"] = pile
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
    assert middle == [], "the discard pile (and any stray card) is cleared from the middle"
    assert g.Mock.ui["statusText"].startswith("Game on!")
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
    assert g.Mock.ui["statusText"].startswith("Game on!")
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
