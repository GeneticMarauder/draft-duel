# MoonSharp (Lua 5.2) in Tabletop Simulator

TTS embeds [MoonSharp](https://www.moonsharp.org/), a C# Lua 5.2 interpreter.
Our tests run real Lua 5.5 under `lupa`, which is more permissive, so code
that passes the tests can still fail to compile in TTS. These are the differences
that bite.

## Syntax TTS rejects

| Construct | Since | Write instead |
| --- | --- | --- |
| `a // b` | 5.3 | `math.floor(a / b)` |
| `&` `\|` `~` `<<` `>>` | 5.3 | arithmetic or `bit32.band` etc. |
| `goto continue` / `::continue::` | 5.2 in reference Lua, **unreliable in MoonSharp** | wrap the loop body in `if … then … end` or a local function with `return` |
| `local x <const>`, `<close>` | 5.4 | plain `local` |
| integer literals that rely on overflow | 5.3 | — |

`tests/test_registry.py` scans every registry sample for these.

## Semantics that differ

- **All numbers are doubles.** `3 / 2 == 1.5`, `math.floor` returns a double,
  `string.format("%d", 2.0)` is fine. Don't rely on `math.type`.
- **`table.unpack`**, not `unpack` (MoonSharp has both, reference Lua 5.2+ only the first).
- **No `require`, no `io`, no `os.execute`.** `os.time`, `os.date`, `os.clock` work.
- **`JSON`** is a TTS global: `JSON.encode(t)`, `JSON.encode_pretty(t)`, `JSON.decode(s)`.
  Empty tables encode as `[]`; decode of invalid JSON throws, so wrap it in `pcall`.
- **Error messages** in TTS show the chunk line, not your source file's line, when the
  builder concatenates files (the Global script here is `draft_core.lua` + `table.lua`
  + a JSON header). Subtract the header lines to find the source line.

## Globals TTS provides

`self` (the object the script is on; `Global` in the Global script), `Global`,
`Player`, `UI`, `Wait`, `JSON`, `Turns`, `Notes`, `Tables`, `Hands`, `Physics`,
`Lighting`, `Info`, `Time`, `WebRequest`, `Color`, `Vector`, plus functions like
`getObjectFromGUID`, `getObjects`, `getObjectsWithTag`, `spawnObject`,
`spawnObjectData`, `group`, `broadcastToAll`, `broadcastToColor`, `printToAll`,
`printToColor`, `log`, `getSeatedPlayers`, `startLuaCoroutine`.

`Vector` and `Color` are TTS classes, but every API that takes them also accepts
plain tables `{x=…, y=…, z=…}` / `{r, g, b}`. The samples use plain tables so they
run under the mock.

## Timing model

Scripts run on the main thread between frames. A long loop freezes the game;
split it with `Wait.frames` or a coroutine (`core/lua-runtime/scripts/wait_patterns.lua`).
`onUpdate` runs every frame — keep it trivial or don't define it.
