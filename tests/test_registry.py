"""Checks the skills registry: manifests, links, sample headers, MoonSharp syntax,
and runs every Lua sample against the TTS mock (plus a few behaviour checks)."""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
from lupa import LuaRuntime

REPO = Path(__file__).resolve().parents[1]
LAYERS = ("router", "mods", "shared", "core")  # highest first: dependencies point down
DOC_DIRS = (*LAYERS, "knowledge", "schemas", "governance")
MOCK = REPO / "tests" / "lua" / "tts_mock.lua"
MOCK_EXTRAS = REPO / "tests" / "lua" / "tts_mock_registry.lua"
SCHEMA = json.loads((REPO / "schemas" / "skill-manifest.schema.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------ discovery


def skill_dirs() -> list[Path]:
    return sorted(p.parent for layer in LAYERS for p in (REPO / layer).rglob("SKILL.md"))


def samples() -> list[Path]:
    return sorted(p for layer in LAYERS for p in (REPO / layer).rglob("scripts/*") if p.is_file())


def lua_samples() -> list[Path]:
    return [p for p in samples() if p.suffix == ".lua"]


def skill_id_for(folder: Path) -> str:
    return ".".join(folder.relative_to(REPO).parts)


def parse_frontmatter(text: str) -> dict[str, Any]:
    """The YAML subset our manifests use: scalars, [] and '- item' lists."""
    match = re.match(r"---\n(.*?)\n---\n", text.replace("\r\n", "\n"), re.DOTALL)
    assert match, "SKILL.md must start with --- frontmatter ---"
    data: dict[str, Any] = {}
    key = None
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        item = re.match(r"\s+-\s+(.*)$", line)
        if item and key is not None:
            data[key].append(item.group(1).strip().strip('"'))
            continue
        kv = re.match(r"([a-z_]+):\s*(.*)$", line)
        assert kv, f"unparseable frontmatter line: {line!r}"
        key, value = kv.group(1), kv.group(2).strip()
        data[key] = [] if value in ("", "[]") else value.strip('"')
    return data


def manifest(folder: Path) -> dict[str, Any]:
    return parse_frontmatter((folder / "SKILL.md").read_text(encoding="utf-8"))


SKILLS = skill_dirs()
IDS = {skill_id_for(d) for d in SKILLS}


# ------------------------------------------------------------------ manifests


@pytest.mark.parametrize("folder", SKILLS, ids=skill_id_for)
def test_manifest_matches_schema_and_folder(folder: Path) -> None:
    m = manifest(folder)
    props = SCHEMA["properties"]
    assert set(SCHEMA["required"]) <= set(m), f"missing: {set(SCHEMA['required']) - set(m)}"
    assert set(m) <= set(props), f"unknown keys: {set(m) - set(props)}"
    for key, rule in props.items():
        value = m[key]
        if "enum" in rule:
            assert value in rule["enum"], f"{key}={value!r} not in {rule['enum']}"
        if rule.get("type") == "array":
            assert isinstance(value, list), f"{key} must be a list"
            for v in value:
                if "pattern" in rule["items"]:
                    assert re.fullmatch(rule["items"]["pattern"], v), f"{key} item {v!r}"
        elif "pattern" in rule:
            assert re.fullmatch(rule["pattern"], value), f"{key}={value!r}"
    assert m["skill_id"] == skill_id_for(folder)
    assert m["layer"] == folder.relative_to(REPO).parts[0]


@pytest.mark.parametrize("folder", SKILLS, ids=skill_id_for)
def test_samples_listed_exist_and_all_are_listed(folder: Path) -> None:
    listed = set(manifest(folder)["samples"])
    present = {f"scripts/{p.name}" for p in (folder / "scripts").glob("*") if p.is_file()}
    assert listed == present


@pytest.mark.parametrize("folder", SKILLS, ids=skill_id_for)
def test_dependencies_exist_and_point_down(folder: Path) -> None:
    m = manifest(folder)
    rank = {layer: i for i, layer in enumerate(reversed(LAYERS))}
    for dep in m["depends_on"]:
        assert dep in IDS, f"unknown dependency {dep}"
        assert rank[dep.split(".")[0]] <= rank[m["layer"]], f"{m['skill_id']} -> {dep} points up"


def test_taxonomy_lists_every_skill() -> None:
    taxonomy = (REPO / "SKILLS_TAXONOMY.md").read_text(encoding="utf-8")
    missing = sorted(i for i in IDS if f"`{i}`" not in taxonomy)
    assert not missing, f"add to SKILLS_TAXONOMY.md: {missing}"


# ------------------------------------------------------------------ links


def markdown_files() -> list[Path]:
    files = [REPO / n for n in ("AGENTS.md", "README.md", "SKILLS_TAXONOMY.md")]
    files += [p for d in DOC_DIRS for p in (REPO / d).rglob("*.md")]
    files += list((REPO / ".claude" / "skills").rglob("*.md"))
    templates = REPO / "governance" / "templates"  # placeholders, links on purpose
    return sorted(f for f in files if templates not in f.parents)


@pytest.mark.parametrize("doc", markdown_files(), ids=lambda p: str(p.relative_to(REPO)))
def test_relative_links_resolve(doc: Path) -> None:
    text = re.sub(r"```.*?```", "", doc.read_text(encoding="utf-8"), flags=re.DOTALL)
    broken = []
    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"[a-z]+:", target) or target.startswith("#"):
            continue
        path = target.split("#", 1)[0]
        if not (doc.parent / path).exists():
            broken.append(target)
    assert not broken, f"broken links: {broken}"


# ------------------------------------------------------------------ sample headers


def owning_skill(sample: Path) -> str:
    return skill_id_for(sample.parent.parent)


@pytest.mark.parametrize("sample", samples(), ids=lambda p: p.name)
def test_sample_header(sample: Path) -> None:
    text = sample.read_text(encoding="utf-8")
    title = f"{owning_skill(sample)} :: {sample.name}"
    if sample.suffix == ".lua":
        first = text.splitlines()[0]
        assert first == f"--[[ {title}", f"first line should be '--[[ {title}'"
        header = text[: text.index("]]")]
        for field in ("Purpose", "Attach", "API", "Use", "Gotchas"):
            assert re.search(rf"^{field}\s*:", header, re.MULTILINE), f"header lacks {field}"
        assert re.search(r"^Verified\s*:\s*(in-game|docs-only)", header, re.MULTILINE), "Verified: in-game|docs-only"
    elif sample.suffix == ".xml":
        assert title in text.split("-->", 1)[0]
        ET.fromstring(f"<root>{text}</root>")  # well-formed apart from having several roots
    else:
        assert text.startswith(f'"""{title}')


# ------------------------------------------------------------------ MoonSharp syntax

_LONG = re.compile(r"\[(=*)\[")
FORBIDDEN = {
    "floor division //": re.compile(r"//"),
    "goto": re.compile(r"\bgoto\b"),
    "<const>/<close>": re.compile(r"<\s*(const|close)\s*>"),
    "bitwise &": re.compile(r"&"),
    "bitwise |": re.compile(r"\|"),
    "bitwise ~": re.compile(r"~(?!=)"),
    "shift << >>": re.compile(r"<<|>>"),
    "bare unpack()": re.compile(r"(?<![\w.])unpack\s*\("),
}


def strip_lua(src: str) -> str:
    """Lua source with comments removed and string contents blanked."""
    out, i, n = [], 0, len(src)
    while i < n:
        if src.startswith("--", i):
            long = _LONG.match(src, i + 2)
            if long:
                end = src.find("]" + long.group(1) + "]", i)
                i = n if end < 0 else end + len(long.group(1)) + 2
            else:
                end = src.find("\n", i)
                i = n if end < 0 else end
            continue
        long = _LONG.match(src, i)
        if long:
            end = src.find("]" + long.group(1) + "]", i)
            i = n if end < 0 else end + len(long.group(1)) + 2
            out.append('""')
            continue
        c = src[i]
        if c in "\"'":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            i = j + 1
            out.append('""')
            continue
        out.append(c)
        i += 1
    return "".join(out)


MOD_LUA = sorted((REPO / "src" / "draft_duel" / "lua").glob("*.lua"))


@pytest.mark.parametrize("script", lua_samples() + MOD_LUA, ids=lambda p: p.name)
def test_lua_is_moonsharp_compatible(script: Path) -> None:
    code = strip_lua(script.read_text(encoding="utf-8"))
    problems = []
    for lineno, line in enumerate(code.splitlines(), 1):
        for name, pattern in FORBIDDEN.items():
            if pattern.search(line):
                problems.append(f"line {lineno}: {name}: {line.strip()}")
    assert not problems, "\n".join(problems)


def test_strip_lua_ignores_comments_and_strings() -> None:
    code = strip_lua('local a = "x // y" -- a // b\nlocal s = [[ goto ]] --[==[ a | b ]==] return a')
    assert "//" not in code and "goto" not in code and "|" not in code
    assert "return a" in code


# ------------------------------------------------------------------ running samples


def to_py(value: Any) -> Any:
    if type(value).__name__ == "_LuaTable":
        d = {k: to_py(v) for k, v in value.items()}
        if d and all(isinstance(k, int) for k in d) and sorted(d) == list(range(1, len(d) + 1)):
            return [d[i] for i in range(1, len(d) + 1)]
        return d
    return value


def runtime(sample: Path | None = None) -> LuaRuntime:
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(MOCK.read_text(encoding="utf-8"))
    lua.execute(MOCK_EXTRAS.read_text(encoding="utf-8"))
    g = lua.globals()
    g.JSON = lua.table(
        encode=lambda t: json.dumps(to_py(t)),
        decode=lambda s: lua.table_from(json.loads(s), recursive=True),
    )
    lua.execute("Mock.setup(20)")
    if sample is not None:
        lua.execute(sample.read_text(encoding="utf-8"))
    return lua


def sample_path(name: str) -> Path:
    (path,) = [p for p in lua_samples() if p.name == name]
    return path


def flush(lua: LuaRuntime) -> None:
    lua.execute("Mock.flush()")


def card(lua: LuaRuntime, guid: str, x: float, z: float, notes: str = "") -> Any:
    return lua.eval(f'(function() local c = Mock.newObject("{guid}", "Card"); '
                    f'c.pos = {{x={x}, y=1, z={z}}}; c.notes = [[{notes}]]; return c end)()')


@pytest.mark.parametrize("sample", lua_samples(), ids=lambda p: p.name)
def test_sample_runs_under_the_mock(sample: Path) -> None:
    lua = runtime(sample)
    if lua.globals().onLoad is not None:
        lua.globals().onLoad("")
    flush(lua)


def test_persistent_state_round_trips_and_migrates() -> None:
    lua = runtime(sample_path("persistent_state.lua"))
    g = lua.globals()
    g.onLoad("")
    g.state.round = 4
    saved = g.onSave()

    again = runtime(sample_path("persistent_state.lua"))
    again.globals().onLoad(saved)
    assert again.globals().state.round == 4

    old = runtime(sample_path("persistent_state.lua"))
    old.globals().onLoad(json.dumps({"version": 1, "turn": 3}))
    assert old.globals().state.round == 3 and old.globals().state.version == 2

    broken = runtime(sample_path("persistent_state.lua"))
    broken.globals().onLoad("{not json")
    assert broken.globals().state.round == 1


def test_seat_relative_layout_mirrors_seats_and_measures_the_felt() -> None:
    lua = runtime(sample_path("seat_relative_layout.lua"))
    g = lua.globals()
    layout = to_py(g.measureLayout("c00001"))
    assert layout["feltY"] == pytest.approx(0.96)
    white, red = to_py(g.toWorld("White", 3, 5)), to_py(g.toWorld("Red", 3, 5))
    assert (white["x"], white["z"]) == (3, -5)
    assert (red["x"], red["z"]) == (-3, 5)


def test_free_spot_avoids_existing_cards() -> None:
    lua = runtime(sample_path("free_spot.lua"))
    g = lua.globals()
    card(lua, "aaaaaa", 0, 5)
    assert not g.spotIsFree(0, 5, 2.2, 3.06, None)
    spot = to_py(g.freeSpotNear(lua.table(x=0, z=5), lua.table(toward=1, rightSign=1)))
    assert abs(spot["x"]) >= 2.2 + 0.3 - 1e-6 or abs(spot["z"] - 5) >= 3.06
    assert g.spotIsFree(spot["x"], spot["z"], 2.2, 3.06, None)


def test_private_cards_hide_from_everyone_else_and_follow_flips() -> None:
    lua = runtime(sample_path("private_cards.lua"))
    g = lua.globals()
    c = card(lua, "bbbbbb", 0, -8)
    g.makePrivate(c, "White", "invisible")
    flush(lua)
    hidden = to_py(c.invisibleTo)
    assert "White" not in hidden and len(hidden) == 11
    flipped = card(lua, "cccccc", 0, -8)
    g.onObjectStateChange(flipped, "bbbbbb")
    flush(lua)
    assert "White" not in to_py(flipped.invisibleTo)
    saved = g.onSave()
    assert "cccccc" in saved and "bbbbbb" not in saved


def test_rules_engine_template_enforces_turns_and_finishes() -> None:
    lua = runtime(sample_path("pure_core_template.lua"))
    g = lua.globals()
    g.onLoad("")
    assert g.tryAct("Red", 1) is False  # White starts
    for _ in range(3):
        assert g.tryAct("White", 2) and g.tryAct("Red", 1)
    assert g.core.finished is True
    assert to_py(g.core.scores) == {"White": 6, "Red": 3}


def test_deck_operations_draw_and_return_into_a_locked_deck() -> None:
    lua = runtime(sample_path("deck_operations.lua"))
    g = lua.globals()
    deck = lua.eval('getObjectFromGUID("c00001")')
    deck.setLock(True)
    cards = g.drawRow(deck, 5, lua.table(x=0, y=1, z=5), lua.table(x=2.5, y=0, z=0), True)
    assert len(to_py(cards)) == 5 and deck.getQuantity() == 15
    g.returnCards(deck, cards)
    flush(lua)
    assert deck.getQuantity() == 20 and deck.locked is True


def test_prevent_merging_only_allows_middle_and_listed_containers() -> None:
    lua = runtime(sample_path("prevent_merging.lua"))
    g = lua.globals()
    deck = lua.eval('getObjectFromGUID("c00001")')
    assert g.tryObjectEnterContainer(deck, card(lua, "dddddd", 0, 6)) is False
    assert g.tryObjectEnterContainer(deck, card(lua, "eeeeee", 0, 0.5)) is True
    g.MERGE_ALLOWED["c00001"] = True
    assert g.tryObjectEnterContainer(deck, card(lua, "ffffff", 0, 6)) is True


def test_chat_commands_dispatch_and_hide_their_messages() -> None:
    lua = runtime(sample_path("chat_commands.lua"))
    g = lua.globals()
    white = lua.eval("Player.White")
    assert g.onChat("!help", white) is False
    assert any("!count" in m for m in to_py(lua.eval("Mock.messages")))
    assert g.onChat("hello", white) is True
    assert g.onChat("!unknown", white) is True


def test_seat_panel_checks_the_seat_and_confirms_twice() -> None:
    lua = runtime(sample_path("seat_panel.lua"))
    g = lua.globals()
    white, red = lua.eval("Player.White"), lua.eval("Player.Red")
    g.onReadyClicked(red, None, "ready_White")
    assert lua.eval('Mock.ui["ready_White.text"]') is None
    g.onReadyClicked(white, None, "ready_White")
    assert lua.eval('Mock.ui["ready_White.text"]') == "Not ready"
    g.onConfirmClicked(white, None, "confirm_White")
    assert lua.eval('Mock.ui["confirm_White.text"]') == "Click again to confirm"
    g.onConfirmClicked(white, None, "confirm_White")
    assert lua.eval('Mock.ui["ready_White.text"]') == "Ready"


def test_context_menus_come_back_after_a_card_is_drawn() -> None:
    lua = runtime(sample_path("context_menus.lua"))
    c = card(lua, "abcabc", 0, 3)
    lua.globals().onObjectLeaveContainer(None, c)
    flush(lua)
    assert [item["label"] for item in to_py(c.menu)] == ["Announce"]


def test_token_spawner_creates_tokens_and_moves_unique_ones() -> None:
    lua = runtime(sample_path("token_spawner.lua"))
    g = lua.globals()
    maker = card(lua, "a1a1a1", 0, 5, '{"id":"example-card-id"}')
    g.addTokenMenu(maker)
    (item,) = to_py(maker.menu)
    assert item["label"] == "Create Treasure"
    item["fn"]("White")
    item["fn"]("White")
    treasures = [o for o in to_py(lua.eval("getObjects()")) if o["name"] == "Treasure"]
    assert len(treasures) == 2
    g.UNIQUE_TOKENS["Treasure"] = True
    item["fn"]("White")
    treasures = [o for o in to_py(lua.eval("getObjects()")) if o["name"] == "Treasure"]
    assert len(treasures) == 2


def test_life_counters_spawn_adjust_and_clear() -> None:
    lua = runtime(sample_path("life_counters.lua"))
    g = lua.globals()
    g.spawnLifeCounters(lua.table(White=lua.table(x=-14, y=1.5, z=-13), Red=lua.table(x=14, y=1.5, z=13)), 20)
    assert g.adjustLife("Red", -3) == 17 and g.lifeOf("Red") == 17 and g.lifeOf("White") == 20
    g.removeLifeCounters()
    assert g.lifeOf("Red") is None


def test_find_objects_filters_by_notes_and_tags() -> None:
    lua = runtime(sample_path("find_objects.lua"))
    g = lua.globals()
    t = card(lua, "c1c1c1", 0, 0, '{"token":"Treasure"}')
    t.addTag("mymod:token")
    found = g.findFirst(lua.table(type="Card", notes=lua.table(token="Treasure")))
    assert found.getGUID() == "c1c1c1"
    assert [o.guid for o in g.byTag("mymod:token").values()] == ["c1c1c1"]
    assert g.byGuid(None) is None
    deck = lua.eval('getObjectFromGUID("c00001")')
    assert len(to_py(g.findInContainer(deck, "Card d00001"))) == 1


def test_spawn_custom_tile_locks_and_disables_the_tile() -> None:
    lua = runtime(sample_path("spawn_custom_tile.lua"))
    tile = lua.globals().spawnImageTile(lua.table(url="https://h/mat.jpg", position=lua.table(x=0, y=1, z=-9.5),
                                                  depth=16, name="mat"))
    flush(lua)
    assert tile.custom.image == "https://h/mat.jpg"
    assert tile.locked is True and tile.interactable is False and tile.scale.x == 8


def test_spawn_card_from_data_builds_card_ids_and_notes() -> None:
    lua = runtime(sample_path("spawn_card_from_data.lua"))
    g = lua.globals()
    data = g.sheetCardData(lua.table(sheetId=3, index=12, face="f", back="b", name="Goblin",
                                     notes=lua.table(token="Goblin")))
    assert data.CardID == 312
    spawned = g.spawnCard(data, lua.table(x=0, y=1, z=0))
    assert to_py(g.readNotes(spawned)) == {"token": "Goblin"}


def test_wait_patterns_cancel_and_run_steps() -> None:
    lua = runtime(sample_path("wait_patterns.lua"))
    lua.globals().startCountdown(3)
    lua.execute("Wait.stop(1)")  # wait ids are sequential: 1 is the countdown's
    flush(lua)
    assert not any("..." in m for m in to_py(lua.eval("Mock.messages")) or [])
    lua.execute("ran = 0; STEP_QUEUE = { function() ran = ran + 1 end, function() ran = ran + 1 end }")
    lua.execute('startLuaCoroutine(Global, "runStepQueue")')
    assert lua.eval("ran") == 2


def test_object_buttons_count_clicks_from_seated_players_only() -> None:
    lua = runtime(sample_path("object_buttons.lua"))
    g = lua.globals()
    c = card(lua, "b0b0b0", 0, 0)
    g.addCounterButton(c)
    g.onCounterClicked(c, "White", False)
    g.onCounterClicked(c, "White", False)
    g.onCounterClicked(c, "White", True)
    g.onCounterClicked(c, "Grey", False)
    assert c.buttons[1].label == "1"
