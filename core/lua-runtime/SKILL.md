---
skill_id: "core.lua-runtime"
name: "Lua Runtime (MoonSharp) and Timing"
description: "TTS's Lua dialect and how to defer work with Wait and coroutines; use before writing any TTS Lua, or when code runs in tests but fails or freezes in the game."
layer: "core"
type: "reference"
execution_mode: "advisory"
version: "0.1.0"
verified: "docs-only"
depends_on: []
samples:
  - "scripts/wait_patterns.lua"
side_effects: []
---

# Lua Runtime (MoonSharp) and Timing

## Purpose

Know which Lua you are writing for and how time works inside TTS, so code that
passes `lupa` tests also compiles and behaves in the game.

## When to use

- Writing any new in-game Lua.
- "Works in the tests, errors in TTS" — usually 5.3+ syntax (see the reference).
- The game hitches or freezes when a script runs a big loop.
- Something must happen "after TTS has finished" a spawn, drop, flip or load.

## How it works

TTS runs MoonSharp (Lua 5.2) on the main thread. Handlers you define as globals
(`onLoad`, `onObjectDrop`, button click functions…) are called by name. To run
code later you schedule it with `Wait`; to spread work across frames you use a
coroutine started with `startLuaCoroutine`. Nothing scheduled survives a reload.

Read [references/moonsharp-lua52.md](references/moonsharp-lua52.md) once.

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/wait_patterns.lua`](scripts/wait_patterns.lua) | `afterFrames`, `every`, `whenReady`, `cancel`, `runSteps` (coroutine queue), a cancellable countdown | Copy the helpers you need into Global or an object script. |

## Gotchas

- (verified) A freshly spawned or dropped object often needs 1–3 frames before
  its state (visibility, position, menu) sticks; `table.lua` re-applies privacy
  3 frames after a drop for this reason.
- (verified) `onLoad` runs before every object is ready; `table.lua` waits 10 frames
  before laying anything out.
- (docs) A coroutine function must be global and `return 1`.
- (docs) `Wait.time(fn, s, -1)` repeats forever; keep the id and `Wait.stop` it.
- (verified) No `//`, no `goto`: MoonSharp rejects them although `lupa` accepts them.

## Testing

The mock's `Wait.frames`/`Wait.time` queue callbacks; `Mock.flush()` runs them all
in order (time is not simulated). `tts_mock_registry.lua` adds `Wait.condition`,
`Wait.stop` and `startLuaCoroutine` (which runs the coroutine to completion).
Frame-exact timing can only be checked in TTS.

## Related

- [`core.state.save-and-load`](../state/save-and-load/SKILL.md) — re-scheduling after a reload.
- [`core.events.event-hooks`](../events/event-hooks/SKILL.md) — which handlers TTS calls.
