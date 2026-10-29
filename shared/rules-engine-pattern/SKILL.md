---
skill_id: "shared.rules-engine-pattern"
name: "Pure Rules Engine + TTS Adapter"
description: "Structure game logic as a pure, serializable Lua engine that returns actions, plus a thin adapter that performs them in TTS; use when adding game rules, a new phase, or starting a new mod."
layer: "shared"
type: "pattern"
execution_mode: "assisted"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.state.save-and-load"
  - "core.lua-testing"
samples:
  - "scripts/pure_core_template.lua"
side_effects: []
---

# Pure Rules Engine + TTS Adapter

## Purpose

Keep the rules testable and the TTS code dumb. The engine decides; the adapter
moves objects.

## When to use

- New rules or phases (a different draft format, a scoring step, turn order).
- Starting a new mod — begin with an engine and its tests before touching TTS.
- A feature whose logic keeps breaking in game: pull the decisions into the engine.

## How it works

```text
player click ──> adapter: tryX(color, objectId) ──> engine:x(color, id)
                                                   │ returns actions or nil, reason
adapter: runActions(actions) <─────────────────────┘
   └─ deal / move / reveal / prompt / discard  (TTS calls)
onSave: JSON.encode(engine:serialize())     onLoad: Engine.restore(data)
```

The engine holds ids and numbers only, has no TTS calls, and returns small action
tables (`{type="deal", color=…, count=…}`). Tests drive it from Python with
nothing mocked. The adapter is the only place that knows about objects,
positions and UI.

In this repo: `draft_core.lua` (`DraftCore.new`, `:start`, `:pick`, `:serialize`,
`.restore`; actions `deal`, `pass`, `pick`, `discard`, `finished`) and `table.lua`'s `runActions`.
`tests/test_draft_lua.py` tests the engine with a tiny Python `FakeTable`, then
the adapter with the mock.

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/pure_core_template.lua`](scripts/pure_core_template.lua) | A complete toy engine (`TurnCore`: turns, rounds, scores, actions, serialize/restore) and its adapter (`runActions`, `tryAct`, `onSave`/`onLoad`) | Start a new engine from it; split into two files when it grows. |

## Gotchas

- (verified) Serialize ids, never objects; `onSave` must produce plain JSON.
- (verified) Keep "who may act" in the engine (`nil, reason`), so bots, buttons and
  chat commands all share one rule.
- (docs) MoonSharp metatables work normally; `setmetatable` + `__index` classes are fine.

## Testing

Engine: call methods from Python and assert on returned actions (see the
`new_core` / `FakeTable` helpers in `tests/test_draft_lua.py`). Adapter: the mock,
including a save → fresh runtime → load round trip.

## Related

- [`core.lua-testing`](../../core/lua-testing/SKILL.md)
- [`mods.draft-duel`](../../mods/draft-duel/SKILL.md)
