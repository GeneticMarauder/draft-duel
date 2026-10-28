"""Runs the real Lua (rules engine + table adapter) under lupa with a mocked TTS API."""

from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
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
        cards[0].menu[1].fn(holder)
        g.Mock.flush()


def _lua_list(t) -> list:
    return [t[i] for i in range(1, len(t) + 1)]


@pytest.mark.parametrize("table_d", [40, 26])
def test_table_adapter_runs_a_whole_draft(table_d: int) -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.Mock.tableD = table_d
    g.onLoad("")
    g.Mock.flush()
    assert g.Mock.ui["startButton.active"] == "true"

    g.onStartClicked(g.Player.White)
    g.Mock.flush()
    assert g.Mock.ui["startButton.active"] == "false"

    holder = g.Mock.packHolder()
    other = "Red" if holder == "White" else "White"
    card = _lua_list(g.Mock.packCards(holder))[0]
    card.menu[1].fn(other)  # opponent tries to draft from someone else's pack
    assert any("not yours" in m for m in _lua_list(g.Mock.messages))

    _play(lua, 96)
    assert g.Mock.ui["statusText"].startswith("Draft complete")
    assert "White 48/48" in g.Mock.ui["statusText"] and "Red 48/48" in g.Mock.ui["statusText"]
    assert len(g.Mock.objects["c00001"].cards) == 515 - 168

    picks = [o for o in g.Mock.objects.values() if o.kind == "Card" and o.rot.z == 0 and o.pos.x != 6]
    white = [o for o in picks if o.pos.z < 0]
    red = [o for o in picks if o.pos.z > 0]
    assert len(white) == 48 and len(red) == 48
    assert all(o.locked for o in picks)
    # Picks never land in the middle strip (cube deck and discard pile live there).
    assert min(abs(o.pos.z) for o in picks) > 3.1 / 2


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
    assert g.Mock.ui["statusText"].startswith("Draft complete")


def test_dropping_a_pack_card_on_the_table_returns_it_to_hand() -> None:
    lua = make_lua(with_table=True)
    g = lua.globals()
    g.Mock.setup(515)
    g.onLoad("")
    g.Mock.flush()
    g.onStartClicked(g.Player.White)
    g.Mock.flush()
    holder = g.Mock.packHolder()
    card = _lua_list(g.Mock.packCards(holder))[0]
    card.setPosition(lua.table(x=0, y=2, z=0))  # dropped in the middle of the table
    g.onObjectDrop(holder, card)
    g.Mock.flush()
    assert len(_lua_list(g.Mock.packCards(holder))) == 4
