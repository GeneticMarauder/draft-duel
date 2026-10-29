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

Builds a Tabletop Simulator (TTS) save for a 1v1 pick-from-5 draft of a
CubeCobra cube (default `LSVCube`). Two halves:

**Python builder** (`uv run lsv-duel-draft [--cube ID] [--push]`)
- `sources.py` — CubeCobra mainboard ids → Scryfall `/cards/collection` → `Card`s; image
  downloads cached in `.cache/images/`. `CARD_SWAPS` replaces cube cards by name with cards we play
  instead (Cogwork Librarian → Booster Tutor); the build prints each swap. Always sends `USER_AGENT`: Scryfall returns 400 for
  generic/library user agents, **including the one TTS itself sends**.
- `sheets.py` — 10x7 JPEG deck sheets (69 cards each; last slot is TTS's hidden-card slot),
  409x570 per card so sheets stay ≤4096 px; content-hashed filenames to defeat TTS's URL cache.
- `tts_save.py` — save JSON: `Table_RPG`, hand zones + hidden zones (fixed GUIDs), the cube deck
  (`c00001`; DFC backs as card state 2 on sheets ≥ 51), Global Lua + XML UI.
- `tokens.py` — tokens from the curated `data/tokens.csv` (one row per token; "Made by" lists cube
  card names separated by `;`, DFCs as "Front // Back"). `match_makers` links them to cube cards by
  name → card id; the build prints maker names no longer in the cube. Token images are downloaded
  through our client like card images and rendered on their own sheets (`TOKEN_SHEET_BASE` 41+:
  fronts, then backs of double-faced tokens).
- `cli.py` — orchestrates; writes `dist/LSV Cube Duel Draft.json`, copies into the TTS Saves
  folder when it exists, `--push` commits `sheets/` so raw.githubusercontent.com URLs resolve.
- Card images are served from this public repo (`sheets/`). TTS cannot load Scryfall images directly.

**Lua (in-game Global script)** — `src/lsv_duel_draft/lua/`
- `draft_core.lua` — pure rules engine (no TTS API). Per pack, starter S / other O:
  S picks, O picks, O picks, S picks — each from 5 cards (`PACK_SIZE`, topped up from the cube), then
  the 4 leftovers are discarded face-up. Starter alternates; 24 packs → 48 picks each (192 cards dealt).
- `table.lua` — TTS adapter. Per side, from the middle out: cube + discard strip, the pack row
  (current pack: 5 cards at 1.5x, side by side, locked, with an on-card **Draft** button and a
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
  `{"id","cmc","land","basic"}`; basic-land card data comes from the `BASIC_LANDS_JSON` script header, token data from `TOKENS_JSON`.
  **Ready to play**: `readyUp` (min 40 cards; bot seats ready automatically) groups the deck into a
  face-down library and the sideboard into a pile invisible to the opponent; when every seat is
  ready, `startGame` removes the land bags, moves the cube and discard pile to the table edges,
  shuffles, deals 7 to each hand and spawns 20-life counters. `ready`, `piles`, `playing` persist.
  **Tokens** (only while `playing`): a card whose GMNotes id is in `TOKENS_JSON.makers` gets a
  right-click "Create <token>" per token; the token spawns in the nearest free card-sized spot beside
  the card (`tokenSpot`: along the row to the owner's right, then left, then rows toward the owner's
  hand; checked against every card/pile/counter's rotated bounds; kept on the owner's battlefield,
  `TOKEN_Z_MIN..MAX`, `|x| <= TOKEN_X_MAX`). A card in hand anchors at `TOKEN_HOME_*` on the
  clicker's side. (Fixed fan-out used to drop tokens on top of neighbouring cards — seen in TTS.) `UNIQUE_TOKENS` (The Monarch,
  Day // Night) move instead of duplicating. Menus are lost when a card enters a deck or on reload, so
  they are re-added on `onObjectSpawn` / `onObjectLeaveContainer` / state change / `onLoad`. Token
  GMNotes are `{"token": label}` (no `id`, so the deck editor ignores them). `addPlayMenu` builds
  these game-time menus.
  **Booster Tutor** (card named `BOOSTER_TUTOR`, right-click "Open a booster"): takes 15 cards from
  the undrafted cube into a face-up, locked row across the middle (revealed to all), each with a
  **Take** button / menu. Only the opener can take; the card goes to their hand, the rest are put
  back face-down into the cube (`returnToCube` unlocks the locked cube around `putObject`), which is
  shuffled. One booster open at a time; `booster` persists. The taken card's GUID goes in `tutored`:
  it only lasts one game.
  **Next game** (top-centre button while `playing`; second click within 4 s confirms) → `nextGame`:
  piles holding owned cards are emptied (all but the last card taken out; the last stays as a plain
  card), then every card is routed by GUID — `owned[color].main/side` (recorded at `readyUp`) back to
  that player's deck/sideboard area, `tutored` back into the cube; tokens and "<color> life" counters
  are destroyed. `building` is set first so `tryObjectEnterContainer` stops returning cards merging into
  piles (the cube is always allowed); returning cards float (gravity off) spread over the columns.
  `gameNumber` increments and the deck editor reopens ("Sideboarding for game N");
  Ready to play starts the next game via the same `readyUp`/`startGame`. `owned`, `tutored` and
  `gameNumber` persist and follow DFC flips in `onObjectStateChange`.
- `ui.xml` — status bar (hidden once the game starts), Start Draft button, Reset view, Next game, per-seat "your pick" prompts.

**Privacy is per card, not hidden zones** (re-applied on every pickup/drop/state change via `rehide`, plus `!hide`). Pack cards use `setHiddenFrom(others)` (opponent sees
backs); picks use `setInvisibleTo(others)`. Hidden zones were dropped: TTS draws them as solid
blocks in the owner's color and ignores their tint. Hand zones exist only to define seats.

**Verified in game (Table_RPG):** felt top y≈0.96, table bounds 64 x 43.
- XML UI in the top-right corner (under TTS's player list) does not receive clicks — keep buttons elsewhere
  (Reset view now sits bottom right, above Ready to play). `UI.setValue` does not relabel a Button; use `setAttribute(id, "text", …)`.
- Cards dropped/placed on each other merge into a deck unless `tryObjectEnterContainer` says no; a locked
  deck refuses `putObject`.
- Testing tip: `/execute <lua>` in chat runs in Global (host only; lines over ~240 chars get cut). After
  typing in chat, the next click on the table only takes focus away from the chat box.

**Tests** — `tests/test_draft_lua.py` runs the real Lua under `lupa` against `tests/lua/tts_mock.lua`
(a mock of the TTS API); keep TTS-specific calls inside the mock's surface or extend the mock.
TTS Lua is MoonSharp (Lua 5.2): no `//`, no `goto`, no integer-only semantics.
<!-- Describe this project's real pipeline / modules here as it takes shape. -->
