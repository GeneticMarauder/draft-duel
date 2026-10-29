"""core.lua-testing :: template_lua_test.py

Template for testing TTS Lua under lupa with the repo's TTS mock.

Copy to ``tests/test_<feature>.py`` (the ``test_`` prefix makes pytest collect it),
point ``SCRIPT`` at the Lua under test and replace the example tests.

Run: ``uv run pytest tests/test_<feature>.py -q``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lupa import LuaRuntime

REPO = Path(__file__).resolve().parents[3]  # when copied to tests/, use parents[1]
MOCK = REPO / "tests" / "lua" / "tts_mock.lua"
MOCK_EXTRAS = REPO / "tests" / "lua" / "tts_mock_registry.lua"
SCRIPT = REPO / "core" / "state" / "save-and-load" / "scripts" / "persistent_state.lua"


def to_py(value: Any) -> Any:
    """Convert Lua tables (recursively) to dicts/lists for assertions."""
    if type(value).__name__ == "_LuaTable":
        d = {k: to_py(v) for k, v in value.items()}
        if d and all(isinstance(k, int) for k in d) and sorted(d) == list(range(1, len(d) + 1)):
            return [d[i] for i in range(1, len(d) + 1)]
        return d
    return value


def make_lua(script: Path = SCRIPT, cube_size: int = 20) -> LuaRuntime:
    """A Lua runtime with the TTS mock, a JSON global and ``script`` loaded."""
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute(MOCK.read_text(encoding="utf-8"))
    lua.execute(MOCK_EXTRAS.read_text(encoding="utf-8"))
    g = lua.globals()
    g.JSON = lua.table(
        encode=lambda t: json.dumps(to_py(t)),
        decode=lambda s: lua.table_from(json.loads(s), recursive=True),
    )
    lua.execute(f"Mock.setup({cube_size})")
    lua.execute(script.read_text(encoding="utf-8"))
    return lua


def test_fresh_load_uses_defaults() -> None:
    lua = make_lua()
    lua.globals().onLoad("")
    lua.execute("Mock.flush()")
    assert lua.globals().state.round == 1


def test_state_survives_save_and_reload() -> None:
    lua = make_lua()
    lua.globals().onLoad("")
    lua.globals().state.round = 4
    saved = lua.globals().onSave()

    reloaded = make_lua()  # a fresh runtime, like TTS loading the save
    reloaded.globals().onLoad(saved)
    reloaded.execute("Mock.flush()")
    assert reloaded.globals().state.round == 4
