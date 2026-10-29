---
skill_id: "core.lua-testing"
name: "Testing TTS Lua under lupa"
description: "Run in-game Lua in pytest against a mock of the TTS API, including save/reload round trips; use for every Lua change before asking the user to test in TTS, and when extending the mock."
layer: "core"
type: "tooling"
execution_mode: "automated"
version: "0.1.0"
verified: "in-game"
depends_on:
  - "core.lua-runtime"
samples:
  - "scripts/template_lua_test.py"
side_effects:
  - "Runs pytest locally; no game or network access."
---

# Testing TTS Lua under lupa

## Purpose

Catch logic errors in seconds, not in a TTS session: the real Lua runs under
[`lupa`](https://pypi.org/project/lupa/) with a Lua stand-in for the TTS API.

## When to use

- Any change to `src/draft_duel/lua/*.lua` or a registry sample.
- Reproducing a bug the user saw in TTS (write the failing test first).
- A new TTS call the mock doesn't know (extend the mock).

## How it works

| File | Role |
| --- | --- |
| `tests/lua/tts_mock.lua` | The mod's mock: objects, decks (`takeObject`/`putObject`/collapse), hands by position, `Wait` queue, `UI`, `group`, `spawnObject(Data)`. `Mock.setup(n)` builds the table; `Mock.flush()` drains `Wait`s. |
| `tests/lua/tts_mock_registry.lua` | Extra API the registry samples use (tags, `Wait.condition`/`stop`, coroutines, `getSeatedPlayers`, `editButton`, counters…). Load after the mock. |
| `tests/test_draft_lua.py` | The mod's tests: full 48-pick drafts, deck editor, game start, tokens, booster, next game, playmats, save/reload mid-draft. |
| `tests/test_registry.py` | Every registry sample loads and runs; manifests, links and MoonSharp syntax are checked. |

`JSON` is provided from Python (`json.dumps`/`json.loads`), as in TTS it is a global.

## Samples

| File | Gives you | Drop it in |
| --- | --- | --- |
| [`scripts/template_lua_test.py`](scripts/template_lua_test.py) | `make_lua()` (mock + extras + JSON + script), `to_py()`, a fresh-load test and a save/reload round-trip test | Copy to `tests/test_<feature>.py`, fix `REPO` to `parents[1]`, change `SCRIPT`. |

## Gotchas

- (verified) `lupa` runs Lua 5.5, far more permissive than MoonSharp: a passing test
  does not prove the code compiles in TTS. Follow
  [`governance/lua-sample-standards.md`](../../governance/lua-sample-standards.md).
- (verified) The mock is only as true as what was observed: when TTS behaves
  differently, fix the mock to match and note it in `knowledge/verified-behaviours.md`.
- (verified) `Mock.flush()` runs every queued `Wait` regardless of delay; tests can't see timing.
- Keep TTS calls inside the mock's surface or extend it — a missing function shows as
  `attempt to call a nil value (field '…')`.

## Testing

```bash
uv run pytest -q                       # everything
uv run pytest tests/test_draft_lua.py -q -k token   # one area
```

## Related

- [`core.state.save-and-load`](../state/save-and-load/SKILL.md) — the round-trip pattern.
- [`governance/review-checklist.md`](../../governance/review-checklist.md)
