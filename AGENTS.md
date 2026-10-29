# AGENTS.md - lsv-duel-draft

Policy layer + architecture for this repo. This file is the source of truth;
`CLAUDE.md` just imports it. Keep it current as the code evolves.

## Ground truth first

Before editing: inspect the actual repo tree and align to files that exist today.
Create new modules only when the task clearly requires them. Treat any
architecture described here as the target, not proof it already exists.

## Tooling — uv only (enforced by a global hook)

- Add a dependency:      `uv add <package>`   (dev: `uv add --group dev <package>`)
- Install / sync:        `uv sync`
- Run something:         `uv run <cmd>`  (e.g. `uv run pytest`)
- **Never** `pip install`, **never** `python -m venv` — the guard hook blocks both.
- Commit `uv.lock`.

## Structure

- src-layout: code in `src/lsv_duel_draft/`, tests in `tests/`.
- Slice by concern (`config`, `io`, `services`, `models`) rather than one module.

## Shared code — reuse agent-core, don't reinvent

Deterministic building blocks (config/`.env` loading, csv/json <-> Pydantic I/O,
logging) come from **agent-core**. Import them instead of re-writing:

```python
from agent_core.config import BaseConfig
from agent_core.io import read_table, validate_records, write_records
from agent_core.utils import get_logger
```

Only add the LLM extra (`agent-core[llm]`) if this project calls an LLM at runtime.

## Definition of done

1. `uv run pytest` passes.
2. Public functions have docstrings and type hints.
3. Ask before adding any new external dependency.

## Architecture

Builds a Tabletop Simulator (TTS) save for a 1v1 pick-from-4 draft of a
CubeCobra cube (default `LSVCube`). Two halves:

**Python builder** (`uv run lsv-duel-draft [--cube ID] [--push]`)
- `sources.py` — CubeCobra mainboard ids → Scryfall `/cards/collection` → `Card`s; image
  downloads cached in `.cache/images/`. Always sends `USER_AGENT`: Scryfall returns 400 for
  generic/library user agents, **including the one TTS itself sends**.
- `sheets.py` — 10x7 JPEG deck sheets (69 cards each; last slot is TTS's hidden-card slot),
  409x570 per card so sheets stay ≤4096 px; content-hashed filenames to defeat TTS's URL cache.
- `tts_save.py` — save JSON: `Table_RPG`, hand zones + hidden zones (fixed GUIDs), the cube deck
  (`c00001`; DFC backs as card state 2 on sheets ≥ 51), Global Lua + XML UI.
- `cli.py` — orchestrates; writes `dist/LSV Cube Duel Draft.json`, copies into the TTS Saves
  folder when it exists, `--push` commits `sheets/` so raw.githubusercontent.com URLs resolve.
- Card images are served from this public repo (`sheets/`). TTS cannot load Scryfall images directly.

**Lua (in-game Global script)** — `src/lsv_duel_draft/lua/`
- `draft_core.lua` — pure rules engine (no TTS API). Per pack, starter S / other O:
  S picks, O picks, O picks, S picks — each from 4 cards (topped up from the cube), then the
  3 leftovers are discarded face-up. Starter alternates; 24 packs → 48 picks each.
- `table.lua` — TTS adapter. Per side, from the middle out: cube + discard strip, the pack row
  (current pack: 4 cards at 1.5x, side by side, locked, with an on-card **Draft** button and a
  right-click "Draft this card"), then the 12x4 pick grid (0.65x). Bots draft for seats empty at
  Start Draft. State persists via `onSave`/`onLoad` (buttons, menus and visibility are reapplied).
  Chat commands: `!draftdebug` (geometry dump), `!draftauto [n]` (random picks for testing).
  **Deck editor** (after pick 96, and on reload of a finished draft): every card on a player's half
  is sorted into columns by mana value (0..7+, then lands), cascaded so names show, gravity off and
  non-sticky so cards stay flat and lift one at a time. The deck is centred on the table; owner-x
  beyond `SIDE_SPLIT_U` is the smaller sideboard (`AREAS`). `onObjectDrop` re-sorts. Basic lands come
  from the land buttons in the bottom panel (`onLandClicked`: left adds, right removes); a basic
  dropped in the sideboard is destroyed.
  `tryObjectEnterContainer` stops cards merging into piles. Card GMNotes carry
  `{"id","cmc","land","basic"}`; basic-land card data comes from the `BASIC_LANDS_JSON` script header.
  **Ready to play**: `readyUp` (min 40 cards; bot seats ready automatically) groups the deck into a
  face-down library and the sideboard into a pile invisible to the opponent; when every seat is
  ready, `startGame` removes the land bags, moves the cube and discard pile to the table edges,
  shuffles, deals 7 to each hand and spawns 20-life counters. `ready`, `piles`, `playing` persist.
- `ui.xml` — status bar, Start Draft button, Reset view, per-seat "your pick" prompts.

**Privacy is per card, not hidden zones** (re-applied on every pickup/drop/state change via `rehide`, plus `!hide`). Pack cards use `setHiddenFrom(others)` (opponent sees
backs); picks use `setInvisibleTo(others)`. Hidden zones were dropped: TTS draws them as solid
blocks in the owner's color and ignores their tint. Hand zones exist only to define seats.

**Verified in game (Table_RPG):** felt top y≈0.96, table bounds 64 x 43.

**Tests** — `tests/test_draft_lua.py` runs the real Lua under `lupa` against `tests/lua/tts_mock.lua`
(a mock of the TTS API); keep TTS-specific calls inside the mock's surface or extend the mock.
TTS Lua is MoonSharp (Lua 5.2): no `//`, no `goto`, no integer-only semantics.
<!-- Describe this project's real pipeline / modules here as it takes shape. -->
